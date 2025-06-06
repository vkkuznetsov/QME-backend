from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.logic.services.report_service.orm import ReportService

router = APIRouter(prefix="/report", tags=["report"])


class ReportRequest(BaseModel):
    report_type: str


class ReportResponse(BaseModel):
    id: int
    report_type: str
    status: str
    created_at: datetime
    download_url: str | None = None


@router.get("/list", response_model=List[ReportResponse])
async def list_reports(report_service: ReportService = Depends()):
    """Получает список доступных отчетов"""
    reports = await report_service.get_available_reports()
    return reports


@router.post("/generate", response_model=ReportResponse)
async def generate_report(
    request: ReportRequest, report_service: ReportService = Depends()
):
    """Генерирует отчет по запросу"""
    report = await report_service.generate_report(
        report_type=request.report_type,
    )
    return report


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(report_id: int, report_service: ReportService = Depends()):
    """Получает информацию о конкретном отчете"""
    report = await report_service.get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.get("/{report_id}/download")
async def download_report(report_id: int, report_service: ReportService = Depends()):
    """Скачивает файл отчета"""
    report = await report_service.get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    if report.status != "completed":
        raise HTTPException(status_code=400, detail="Report is not ready for download")

    file_path = report_service._get_report_path(report_id)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Report file not found")

    return FileResponse(
        path=file_path,
        filename=f"report_{report_id}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
