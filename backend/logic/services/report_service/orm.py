from pathlib import Path

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.database import db_session
from backend.database.models.elective import Elective
from backend.database.models.group import Group
from backend.database.models.manager import Manager
from backend.database.models.report import Report
from backend.database.models.student import Student, student_group
from backend.database.models.transfer import Transfer
from backend.logic.services.log_service.orm import DatabaseLogger

log = DatabaseLogger(__name__)


class ReportService:
    REPORTS_DIR = Path("reports")

    def __init__(self):
        self.REPORTS_DIR.mkdir(exist_ok=True)

    def _get_report_path(self, report_id: int) -> Path:
        """Получает путь к файлу отчета"""
        return self.REPORTS_DIR / f"report_{report_id}.xlsx"

    @db_session
    async def generate_report(self, report_type: str, db: AsyncSession) -> Report:
        """Генерирует отчет и сохраняет его в базе данных"""
        try:
            # Создаем запись об отчете
            report = Report(
                report_type=report_type,
                status="generating",
            )
            db.add(report)
            await db.flush()

            # Генерируем отчет в зависимости от типа
            match report_type:
                case "student_transfers":
                    await self._generate_student_transfers_report(report, db)
                case "elective_statistics":
                    await self._generate_elective_statistics_report(report, db)
                case "manager_actions":
                    await self._generate_manager_actions_report(report, db)
                case _:
                    raise ValueError(f"Неизвестный тип отчета: {report_type}")

            # Обновляем статус и URL для скачивания
            report.status = "completed"
            report.download_url = f"/reports/{report.id}.xlsx"
            await db.commit()

            return report

        except Exception as e:
            report.status = "failed"
            await db.commit()
            raise e

    async def _generate_student_transfers_report(
            self, report: Report, db: AsyncSession
    ):
        from sqlalchemy.orm import aliased

        # Создаем псевдонимы
        FromElective = aliased(Elective, name="from_elective")
        ToElective = aliased(Elective, name="to_elective")
        """Генерирует отчет по переводам студентов"""
        # Получаем данные о переводах
        query = (
            select(
                Transfer.id,
                Student.fio.label("student_name"),
                FromElective.name.label("from_elective"),
                ToElective.name.label("to_elective"),
                Transfer.status,
                Transfer.created_at,
                Transfer.priority,
                Manager.name.label("manager_name"),
            )
            .join(Student, Transfer.student_id == Student.id)
            .join(FromElective, Transfer.from_elective_id == FromElective.id)
            .join(ToElective, Transfer.to_elective_id == ToElective.id)
            .outerjoin(Manager, Transfer.manager_id == Manager.id)
            .order_by(Transfer.created_at.desc())
        )
        result = await db.execute(query)
        transfers = result.all()

        # Создаем Excel файл
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Переводы студентов"

        # Заголовки
        headers = [
            "ID",
            "Студент",
            "Из электива",
            "В электив",
            "Статус",
            "Дата создания",
            "Приоритет",
            "Менеджер",
        ]
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col)
            cell.value = header
            cell.font = Font(bold=True)
            cell.fill = PatternFill(
                start_color="CCCCCC", end_color="CCCCCC", fill_type="solid"
            )
            cell.alignment = Alignment(horizontal="center")

        # Данные
        for row, transfer in enumerate(transfers, 2):
            ws.cell(row=row, column=1).value = transfer.id
            ws.cell(row=row, column=2).value = transfer.student_name
            ws.cell(row=row, column=3).value = transfer.from_elective
            ws.cell(row=row, column=4).value = transfer.to_elective
            ws.cell(row=row, column=5).value = transfer.status
            ws.cell(row=row, column=6).value = transfer.created_at
            ws.cell(row=row, column=7).value = transfer.priority
            ws.cell(row=row, column=8).value = transfer.manager_name

        # Автоматическая ширина столбцов
        for col in range(1, len(headers) + 1):
            ws.column_dimensions[get_column_letter(col)].auto_size = True

        # Сохраняем файл
        file_path = self._get_report_path(report.id)
        wb.save(file_path)

    async def _generate_elective_statistics_report(
            self, report: Report, db: AsyncSession
    ):
        """Генерирует статистику по элективам"""
        # Получаем статистику по элективам
        query = (
            select(
                Elective.id,
                Elective.name,
                Elective.cluster,
                func.count(func.distinct(Student.id)).label("student_count"),
                func.count(func.distinct(Transfer.id)).label("transfer_count"),
                func.count(
                    func.distinct(
                        case((Transfer.status == "approved", Transfer.id), else_=None)
                    )
                ).label("approved_transfers"),
            )
            .outerjoin(Group, Elective.id == Group.elective_id)
            .outerjoin(student_group, Group.id == student_group.c.group_id)
            .outerjoin(Student, student_group.c.student_id == Student.id)
            .outerjoin(
                Transfer,
                (Elective.id == Transfer.from_elective_id)
                | (Elective.id == Transfer.to_elective_id),
            )
            .group_by(Elective.id, Elective.name, Elective.cluster)
            .order_by(Elective.cluster, Elective.name)
        )
        result = await db.execute(query)
        statistics = result.all()

        # Создаем Excel файл
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Статистика элективов"

        # Заголовки
        headers = [
            "ID",
            "Название",
            "Кластер",
            "Количество студентов",
            "Количество заявок",
            "Одобренных заявок",
        ]
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col)
            cell.value = header
            cell.font = Font(bold=True)
            cell.fill = PatternFill(
                start_color="CCCCCC", end_color="CCCCCC", fill_type="solid"
            )
            cell.alignment = Alignment(horizontal="center")

        # Данные
        for row, stat in enumerate(statistics, 2):
            ws.cell(row=row, column=1).value = stat.id
            ws.cell(row=row, column=2).value = stat.name
            ws.cell(row=row, column=3).value = stat.cluster
            ws.cell(row=row, column=4).value = stat.student_count
            ws.cell(row=row, column=5).value = stat.transfer_count
            ws.cell(row=row, column=6).value = stat.approved_transfers

        # Автоматическая ширина столбцов
        for col in range(1, len(headers) + 1):
            ws.column_dimensions[get_column_letter(col)].auto_size = True

        # Сохраняем файл
        file_path = self._get_report_path(report.id)
        wb.save(file_path)

    async def _generate_manager_actions_report(self, report: Report, db: AsyncSession):
        """Генерирует отчет по действиям менеджеров"""
        # Получаем данные о действиях менеджеров
        query = (
            select(
                Manager.name.label("manager_name"),
                func.count(func.distinct(Transfer.id)).label("total_transfers"),
                func.count(
                    func.distinct(
                        case((Transfer.status == "approved", Transfer.id), else_=None)
                    )
                ).label("approved_transfers"),
                func.count(
                    func.distinct(
                        case((Transfer.status == "rejected", Transfer.id), else_=None)
                    )
                ).label("rejected_transfers"),
                func.max(Transfer.created_at).label("last_action"),
            )
            .outerjoin(Transfer, Manager.id == Transfer.manager_id)
            .group_by(Manager.id, Manager.name)
            .order_by(func.count(func.distinct(Transfer.id)).desc())
        )
        result = await db.execute(query)
        actions = result.all()

        # Создаем Excel файл
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Действия менеджеров"

        # Заголовки
        headers = [
            "Менеджер",
            "Всего заявок",
            "Одобрено",
            "Отклонено",
            "Последнее действие",
        ]
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col)
            cell.value = header
            cell.font = Font(bold=True)
            cell.fill = PatternFill(
                start_color="CCCCCC", end_color="CCCCCC", fill_type="solid"
            )
            cell.alignment = Alignment(horizontal="center")

        # Данные
        for row, action in enumerate(actions, 2):
            ws.cell(row=row, column=1).value = action.manager_name
            ws.cell(row=row, column=2).value = action.total_transfers
            ws.cell(row=row, column=3).value = action.approved_transfers
            ws.cell(row=row, column=4).value = action.rejected_transfers
            ws.cell(row=row, column=5).value = action.last_action

        # Автоматическая ширина столбцов
        for col in range(1, len(headers) + 1):
            ws.column_dimensions[get_column_letter(col)].auto_size = True

        # Сохраняем файл
        file_path = self._get_report_path(report.id)
        wb.save(file_path)

    @db_session
    async def get_available_reports(self, db: AsyncSession) -> list[Report]:
        """Получает список доступных отчетов"""
        result = await db.execute(select(Report).order_by(Report.created_at.desc()))
        return list(result.scalars().all())

    @db_session
    async def get_report(self, report_id: int, db: AsyncSession) -> Report:
        """Получает информацию о конкретном отчете"""
        report = await db.get(Report, report_id)
        return report
