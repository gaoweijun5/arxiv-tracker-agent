"""Research report API endpoints."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.database import get_db, ResearchReport, Paper

router = APIRouter(prefix="/reports", tags=["reports"])


class ResearchReportResponse(BaseModel):
    """Research report response model."""

    id: int
    fetch_log_id: Optional[int]
    source: str
    title: str
    summary: Optional[str]
    content_md: str
    paper_ids: list[int]
    stats: dict
    status: str
    error_message: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]
    papers: list[dict] = []


class ResearchReportListResponse(BaseModel):
    """Paginated research report list response."""

    reports: list[ResearchReportResponse]
    total: int
    page: int
    page_size: int


async def _paper_dicts(db: AsyncSession, paper_ids: list[int]) -> list[dict]:
    if not paper_ids:
        return []
    result = await db.execute(select(Paper).where(Paper.id.in_(paper_ids)))
    papers = result.scalars().all()
    by_id = {paper.id: paper for paper in papers}
    return [by_id[paper_id].to_dict() for paper_id in paper_ids if paper_id in by_id]


async def _report_response(db: AsyncSession, report: ResearchReport) -> ResearchReportResponse:
    data = report.to_dict()
    data["papers"] = await _paper_dicts(db, data["paper_ids"])
    return ResearchReportResponse(**data)


@router.get("", response_model=ResearchReportListResponse)
async def list_reports(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    source: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List generated research reports."""
    query = select(ResearchReport)
    count_query = select(func.count(ResearchReport.id))

    if source:
        query = query.where(ResearchReport.source == source)
        count_query = count_query.where(ResearchReport.source == source)

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(ResearchReport.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    reports = result.scalars().all()

    return ResearchReportListResponse(
        reports=[await _report_response(db, report) for report in reports],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/latest", response_model=Optional[ResearchReportResponse])
async def get_latest_report(
    source: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get the latest generated research report."""
    query = select(ResearchReport)
    if source:
        query = query.where(ResearchReport.source == source)

    result = await db.execute(query.order_by(ResearchReport.created_at.desc()).limit(1))
    report = result.scalar_one_or_none()
    if not report:
        return None
    return await _report_response(db, report)


@router.get("/{report_id}", response_model=ResearchReportResponse)
async def get_report(report_id: int, db: AsyncSession = Depends(get_db)):
    """Get one research report."""
    result = await db.execute(select(ResearchReport).where(ResearchReport.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Research report not found")
    return await _report_response(db, report)
