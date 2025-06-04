from typing import List, Optional
from pathlib import Path
import json
import onnxruntime as ort

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from backend.database.database import db_session
from backend.database.models.elective import Elective
from backend.database.models.group import Group
from backend.database.models.student import Student
from backend.database.models.student import student_group

from backend.logic.services.student_service.base import IStudentService

from logging import getLogger

log = getLogger(__name__)

# Globals for lazy loading
code2idx = {}
prof2idx = {}
onnx_sess = None


class ORMStudentService(IStudentService):
    @db_session  # TODO: переделать на EXISTS для оптимизации
    async def get_student_by_email(
            self,
            student_email: str,
            db: AsyncSession
    ) -> Optional[Student]:
        """
        Получить студента по email без загрузки связанных сущностей.

        Args:
            student_email (str): Email студента.
            db (AsyncSession): Асинхронная сессия SQLAlchemy.

        Returns:
            Optional[Student]: Объект Student, если найден, иначе None.
        """
        query = select(Student).where(Student.email == student_email).limit(1)
        student: Optional[Student] = await db.scalar(query)
        return student

    @db_session
    async def get_student_group_elective_email(
            self,
            student_email: str,
            db: AsyncSession
    ) -> Optional[Student]:
        """
        Получить студента по email вместе с его группами и элективами.

        Загрузка происходит через joinedload, чтобы избежать N+1 проблем.

        Args:
            student_email (str): Email студента.
            db (AsyncSession): Асинхронная сессия SQLAlchemy.

        Returns:
            Optional[Student]: Объект Student с загруженными группами и элективами, иначе None.
        """
        query = (
            select(Student)
            .options(joinedload(Student.groups).joinedload(Group.elective))
            .where(Student.email == student_email)
        )
        result = await db.execute(query)
        student: Optional[Student] = result.unique().scalar_one_or_none()
        return student

    @db_session
    async def get_all_student_group_elective_email(
            self,
            db: AsyncSession,
            start: int,
            limit: int
    ) -> List[Student]:
        """
        Получить список студентов с пагинацией без загрузки связанных сущностей.

        Args:
            db (AsyncSession): Асинхронная сессия SQLAlchemy.
            start (int): Смещение для начала выборки.
            limit (int): Максимальное количество возвращаемых записей.

        Returns:
            List[Student]: Список объектов Student (может быть пустым).
        """
        query = (
            select(Student)
            .offset(start)
            .limit(limit)
        )
        result = await db.execute(query)
        students_list = result.unique().scalars().all()
        students: List[Student] = list(students_list)
        return students

    @db_session
    async def get_staistic(self, direction: str, db: AsyncSession):
        total_students_query = select(func.count(Student.id)).where(
            Student.sp_code == direction
        )
        total_students = await db.scalar(total_students_query)

        if not total_students:
            return []

        # Сначала получаем данные по курсам
        subquery = (
            select(
                Elective.cluster,
                Elective.id,
                Elective.name,
                func.count(Student.id.distinct()).label("course_student_count"),
            )
            .select_from(Student)
            .join(student_group)
            .join(Group)
            .join(Elective)
            .where(Student.sp_code == direction)
            .group_by(Elective.cluster, Elective.id, Elective.name)
            .subquery()
        )

        # Затем агрегируем по кластерам
        stmt = select(
            subquery.c.cluster,
            func.sum(subquery.c.course_student_count).label("total_students"),
            func.json_agg(
                func.json_build_object(
                    "id",
                    subquery.c.id,
                    "name",
                    subquery.c.name,
                    "student_count",
                    subquery.c.course_student_count,
                )
            ).label("courses"),
        ).group_by(subquery.c.cluster)

        result = await db.execute(stmt)
        clusters_data = result.all()

        recommendations = []
        for cluster, students_count, courses in clusters_data:
            sorted_courses = sorted(
                [dict(c) for c in courses],
                key=lambda x: x["student_count"],
                reverse=True,
            )[:5]

            cluster_percent = round((students_count / total_students) * 100, 1)
            if cluster_percent <= 0:
                continue

            recommendations.append(
                {
                    "name": cluster,
                    "percent": cluster_percent,
                    "totalStudents": students_count,
                    "topCourses": [
                        {
                            **course,
                            "percent": round(
                                (course["student_count"] / total_students) * 100, 1
                            ),
                        }
                        for course in sorted_courses
                    ],
                }
            )

        return sorted(recommendations, key=lambda x: x["percent"], reverse=True)[:5]

    async def get_student_groups_for_elective(self, student_id: int, elective_id: int, db: AsyncSession) -> list[Group]:
        query = (
            select(Group)
            .join(student_group)
            .where(
                student_group.c.student_id == student_id,
                Group.elective_id == elective_id
            )
        )
        result = await db.execute(query)
        groups = result.unique().scalars().all()
        return groups

    @db_session
    async def get_student_recommendation(
            self,
            student_id: int,
            db: AsyncSession,
            top_k: int = 5
    ):
        """
        Получить рекомендации для студента по ID с помощью ONNX-модели,
        используя лени­вую инициализацию code2idx, prof2idx и onnx_sess.
        """
        import numpy as np
        global code2idx, prof2idx, onnx_sess

        # Lazy initialization of code2idx, prof2idx, and onnx_sess
        if not code2idx or not prof2idx or onnx_sess is None:
            base = Path(__file__).resolve().parents[4]
            code_path = base / "code_list.json"
            profile_path = base / "profile_list.json"
            code_list = json.loads(code_path.read_text(encoding="utf-8"))
            profile_list = json.loads(profile_path.read_text(encoding="utf-8"))
            code2idx.clear()
            prof2idx.clear()
            code2idx.update({c: i for i, c in enumerate(code_list)})
            prof2idx.update({p: i for i, p in enumerate(profile_list)})
            onnx_sess = ort.InferenceSession(str(base / "student_tower.onnx"), providers=["CPUExecutionProvider"])

        # 1. Проверяем, что студент существует
        student = await db.get(Student, student_id)
        if not student:
            log.warning(f"Student with id={student_id} not found")
            return None


        # 2. Формируем числовые признаки студента
        num_feats = np.hstack([
            np.array(student.competencies, dtype=np.float32),
            np.array(list(student.diagnostics.values()), dtype=np.float32)
        ]).reshape(1, -1).astype(np.float32)

        # 3. Получаем индексы code_idx и prof_idx из кэша
        code_idx_val = code2idx.get(student.sp_code)
        prof_idx_val = prof2idx.get(student.sp_profile)
        if code_idx_val is None or prof_idx_val is None:
            return {"student_id": student_id, "recommendations": []}

        code_idx = np.array([code_idx_val], dtype=np.int64)
        prof_idx = np.array([prof_idx_val], dtype=np.int64)

        # 4. Выполняем инференс ONNX
        inputs = {
            onnx_sess.get_inputs()[0].name: num_feats,
            onnx_sess.get_inputs()[1].name: code_idx,
            onnx_sess.get_inputs()[2].name: prof_idx
        }
        student_embed = onnx_sess.run(None, inputs)[0]  # shape=(1, D)

        # 5. Загружаем все элективы с непустым text_embed
        res_els = await db.execute(select(Elective).where(Elective.text_embed.isnot(None)))
        electives = res_els.scalars().all()
        if not electives:
            return {"student_id": student_id, "recommendations": []}

        # 6. Формируем матрицу эмбеддингов элективов и список ID
        item_embeds = []
        item_ids = []
        for e in electives:
            item_embeds.append(np.array(e.text_embed, dtype=np.float32))
            item_ids.append(e.id)
        X_items = np.vstack(item_embeds)  # shape=(N_items, D)

        # 7. Вычисляем сходство и возвращаем top_k рекомендаций
        sims = (student_embed @ X_items.T).flatten()  # shape=(N_items,)
        topk_idx = np.argsort(sims)[::-1][:top_k]
        top_item_ids = [item_ids[i] for i in topk_idx]


        # Получаем полные объекты элективов по top_item_ids
        rec_electives_result = await db.execute(
            select(Elective).where(Elective.id.in_(top_item_ids))
        )
        rec_electives = rec_electives_result.scalars().all()

        from collections import defaultdict

        recommendations = []
        for e in rec_electives:
            # Загружаем группы по элективу с joinedload студентов
            res_groups = await db.execute(
                select(Group).where(Group.elective_id == e.id).options(joinedload(Group.students))
            )
            groups = res_groups.unique().scalars().all()

            # Группируем по типу
            type_to_groups = defaultdict(list)
            for g in groups:
                type_to_groups[g.type].append(g)

            # Для каждого типа суммируем все свободные места
            free_spots_per_type = []
            for type_groups in type_to_groups.values():
                total_free_in_type = sum(g.capacity - len(g.students) for g in type_groups)
                free_spots_per_type.append(total_free_in_type)

            # Общее количество мест = минимальное из доступных по типам
            total_free_spots = min(free_spots_per_type) if free_spots_per_type else 0

            recommendations.append(
                {
                    "id": e.id,
                    "name": e.name,
                    "description": e.description,
                    "cluster": e.cluster,
                    "free_spots": total_free_spots,
                }
            )

        return {
            "student_id": student_id,
            "recommendations": recommendations
        }
