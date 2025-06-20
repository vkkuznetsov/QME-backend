import json
from logging import getLogger
from pathlib import Path
from typing import List, Optional

import onnxruntime as ort
from sqlalchemy import select, func, exists
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from backend.database.database import db_session
from backend.database.models.elective import Elective
from backend.database.models.group import Group
from backend.database.models.student import Student
from backend.database.models.student import student_group
from backend.database.models.transfer import Transfer
from backend.logic.services.student_service.base import IStudentService

log = getLogger(__name__)

# Globals for lazy loading
code2idx = {}
prof2idx = {}
onnx_sess = None
item_sess = None
mu_vec = None
sigma_vec = None


class ORMStudentService(IStudentService):
    @db_session  # TODO: переделать на EXISTS для оптимизации
    async def get_student_by_email(
            self, student_email: str, db: AsyncSession
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
            self, student_email: str, db: AsyncSession
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
            self, db: AsyncSession, start: int, limit: int
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
        query = select(Student).offset(start).limit(limit)
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
                            "cluster": cluster,
                            "percent": round(
                                (course["student_count"] / total_students) * 100, 1
                            ),
                            "free_spots": (
                                (await db.scalar(
                                    select(func.sum(Group.capacity))
                                    .where(Group.elective_id == course["id"])
                                )) or 0
                            ) - course["student_count"],
                        }
                        for course in sorted_courses
                    ],
                }
            )

        return sorted(recommendations, key=lambda x: x["percent"], reverse=True)[:5]

    @db_session
    async def get_student_groups_for_elective(
            self, student_id: int, elective_id: int, db: AsyncSession
    ) -> list[Group]:
        query = (
            select(Group)
            .join(student_group)
            .where(
                student_group.c.student_id == student_id,
                Group.elective_id == elective_id,
            )
        )
        result = await db.execute(query)
        groups = result.unique().scalars().all()
        return groups

    @db_session
    async def get_student_recommendation(
            self, student_id: int, db: AsyncSession, top_k: int = 10
    ):
        """
        Получить рекомендации для студента по ID с помощью ONNX-модели,
        используя лени­вую инициализацию code2idx, prof2idx и onnx_sess.
        """
        import numpy as np

        global code2idx, prof2idx, onnx_sess, item_sess, mu_vec, sigma_vec

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
            onnx_sess = ort.InferenceSession(
                str(base / "student_tower.onnx"), providers=["CPUExecutionProvider"]
            )
            item_sess = ort.InferenceSession(str(base / "item_tower.onnx"),
                                             providers=["CPUExecutionProvider"])
            stats = json.loads((base / "num_stats.json").read_text(encoding="utf-8"))
            mu_vec = np.array(stats["mu"], dtype=np.float32).reshape(1, -1)
            sigma_vec = np.array(stats["sigma"], dtype=np.float32).reshape(1, -1) + 1e-9

        # 1. Проверяем, что студент существует
        student = await db.get(Student, student_id)
        if not student:
            log.warning(f"Student with id={student_id} not found")
            return None

        # 2. Формируем числовые признаки студента
        num_feats = np.hstack([
            np.array(list(student.competencies.values()), dtype=np.float32),
            np.array(list(student.diagnostics.values()), dtype=np.float32)
        ]).reshape(1, -1)
        num_feats = (num_feats - mu_vec) / sigma_vec

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
            onnx_sess.get_inputs()[2].name: prof_idx,
        }
        student_embed = onnx_sess.run(None, inputs)[0]  # shape=(1, D)

        # 5. Загружаем все элективы с непустым text_embed
        res_els = await db.execute(
            select(Elective).where(Elective.text_embed.isnot(None))
        )
        electives = res_els.scalars().all()
        if not electives:
            return {"student_id": student_id, "recommendations": []}

        # 6-7. Формируем матрицу эмбеддингов элективов, применяем item_sess и вычисляем сходство
        item_embeds_raw, item_ids = [], []
        for e in electives:
            item_embeds_raw.append(np.array(e.text_embed, dtype=np.float32))
            item_ids.append(e.id)
        X_items_raw = np.vstack(item_embeds_raw).astype(np.float32)
        item_embeds = item_sess.run(
            None, {item_sess.get_inputs()[0].name: X_items_raw}
        )[0]
        sims = (student_embed @ item_embeds.T).flatten()
        topk_idx = np.argsort(sims)[::-1][:top_k]
        top_item_ids = [item_ids[i] for i in topk_idx]

        # подсчёт желающих (трансферов) для рекомендованных элективов
        counts_res = await db.execute(
            select(
                Transfer.to_elective_id.label("eid"),
                func.count(Transfer.id).label("transfer_count"),
            )
            .where(Transfer.to_elective_id.in_(top_item_ids))
            .group_by(Transfer.to_elective_id)
        )
        transfer_counts = {row.eid: row.transfer_count for row in counts_res.all()}

        # Получаем полные объекты элективов по top_item_ids
        rec_electives_result = await db.execute(
            select(Elective).where(Elective.id.in_(top_item_ids))
        )
        rec_electives = rec_electives_result.scalars().all()

        from collections import defaultdict

        id2elective = {e.id: e for e in rec_electives}

        recommendations = []
        for eid in top_item_ids:
            e = id2elective[eid]
            # Загружаем группы по элективу с joinedload студентов
            res_groups = await db.execute(
                select(Group)
                .where(Group.elective_id == e.id)
                .options(joinedload(Group.students))
            )
            groups = res_groups.unique().scalars().all()

            # Группируем по типу
            type_to_groups = defaultdict(list)
            for g in groups:
                type_to_groups[g.type].append(g)

            # Для каждого типа суммируем все свободные места
            free_spots_per_type = []
            for type_groups in type_to_groups.values():
                total_free_in_type = sum(
                    g.capacity - len(g.students) for g in type_groups
                )
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
                    "transfer_count": transfer_counts.get(e.id, 0),
                }
            )

        return {"student_id": student_id, "recommendations": recommendations}

    @db_session
    async def can_student_transfer(self, student_id: int, elective_id: int, db: AsyncSession):
        has_transfer = await db.scalar(
            select(
                exists().where(
                    Transfer.student_id == student_id,
                    Transfer.to_elective_id == elective_id,
                    Transfer.status == 'pending',
                )
            )
        )
        if has_transfer:
            return {
                "can_transfer": False,
                "reason": "already_pending",
                "message": "Заявка уже подана и ожидает рассмотрения."
            }

        is_enrolled = await db.scalar(
            select(
                exists().where(
                    Group.elective_id == elective_id,
                    Group.students.any(Student.id == student_id)
                )
            )
        )
        if is_enrolled:
            return {
                "can_transfer": False,
                "reason": "already_enrolled",
                "message": "Вы уже записаны на этот электив."
            }

        return {"can_transfer": True}
