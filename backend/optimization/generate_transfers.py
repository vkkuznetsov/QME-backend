import asyncio
import random
from datetime import datetime, timedelta, UTC
import argparse

from sqlalchemy import select, insert
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.database import db_session
from backend.database.models.transfer import Transfer, TransferStatus, transfer_group, GroupRole
from backend.database.models.group import Group
from backend.database.models.elective import Elective
from backend.database.models.student import Student


@db_session
async def generate_transfer(num_students: int, db: AsyncSession):
        # Получаем все элективы
        result = await db.execute(select(Elective))
        electives = result.scalars().all()
        elective_ids = [e.id for e in electives]

        # Для каждого студента
        for student_id in range(1, num_students + 1):
            # Получаем студента
            result = await db.execute(select(Student).filter(Student.id == student_id).options(selectinload(Student.groups)))
            student = result.scalar_one_or_none()
            if not student:
                print(f"Student with id {student_id} not found. Skipping.")
                continue

            # Гарантируем загрузку связанных групп (если используется ленивый режим, можно явно их запросить)
            # Предполагаем, что student.groups уже загружены
            if not student.groups:
                print(f"Student {student_id} has no groups. Skipping.")
                continue

            # Группируем группы студента по elective_id
            student_groups_by_elective = {}
            for grp in student.groups:
                student_groups_by_elective.setdefault(grp.elective_id, []).append(grp)

            # Для каждого электива, на котором студент уже учится (from_elective)
            for from_elective_id, from_groups in student_groups_by_elective.items():
                # Выбираем 5 случайных target элективов, отличных от текущего
                possible_targets = [eid for eid in elective_ids if eid != from_elective_id]
                if not possible_targets:
                    continue
                target_electives = random.sample(possible_targets, min(5, len(possible_targets)))
                
                # Фильтруем элективы, у которых есть группы
                valid_targets = []
                for target_elective_id in target_electives:
                    result_groups = await db.execute(select(Group).filter(Group.elective_id == target_elective_id))
                    target_groups = result_groups.scalars().all()
                    if target_groups:
                        valid_targets.append(target_elective_id)

                for i, target_elective_id in enumerate(valid_targets, start=1):
                    # Создаем запись Transfer
                    created_at = (datetime.now(UTC) - timedelta(seconds=random.randint(0, 86400))).replace(tzinfo=None)
                    priority = i
                    transfer = Transfer(
                        student_id=student_id,
                        from_elective_id=from_elective_id,
                        to_elective_id=target_elective_id,
                        priority=priority,
                        created_at=created_at,
                        status=TransferStatus.pending
                    )
                    db.add(transfer)
                    await db.flush()  # чтобы получить transfer.id

                    association_rows = []

                    # Для groups_from: берем все группы студента, относящиеся к from_elective
                    for grp in from_groups:
                        association_rows.append({
                            'transfer_id': transfer.id,
                            'group_id': grp.id,
                            'group_role': GroupRole.FROM
                        })

                    # Для groups_to: выбираем по 1 группе каждого уникального типа из групп target электива
                    result_groups = await db.execute(select(Group).filter(Group.elective_id == target_elective_id))
                    target_groups = result_groups.scalars().all()

                    groups_by_type = {}
                    for grp in target_groups:
                        groups_by_type.setdefault(grp.type, []).append(grp)

                    for grp_type, groups_list in groups_by_type.items():
                        chosen_group = random.choice(groups_list)
                        association_rows.append({
                            'transfer_id': transfer.id,
                            'group_id': chosen_group.id,
                            'group_role': GroupRole.TO
                        })

                    # Вставляем записи в таблицу transfer_group
                    await db.execute(insert(transfer_group), association_rows)
        await db.commit()
        print("Transfers generated.")


def main():
    parser = argparse.ArgumentParser(description="Generate transfers based on existing student enrollments")
    parser.add_argument("students", type=int, help="Number of students to process")
    args = parser.parse_args()
    asyncio.run(generate_transfer(args.students))


if __name__ == '__main__':
    main()