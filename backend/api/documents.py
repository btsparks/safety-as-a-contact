"""API endpoints for safety document management."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.api.deps import get_db
from backend.documents.ingestion import ingest_document
from backend.documents.retrieval import retrieve_relevant_documents
from backend.models import SafetyDocument

router = APIRouter(prefix="/api/documents", tags=["documents"])


class DocumentUploadRequest(BaseModel):
    project_id: int | None = None
    title: str
    content: str
    category: str
    trade_tags: list[str] | None = None
    hazard_tags: list[str] | None = None
    language: str = "en"


class DocumentSearchRequest(BaseModel):
    project_id: int | None = None
    trade: str = "general"
    observation_text: str
    max_results: int = 3


@router.post("/upload")
async def upload_document(
    req: DocumentUploadRequest,
    db: Session = Depends(get_db),
):
    """Upload a safety document for the reference library."""
    docs = ingest_document(
        db=db,
        project_id=req.project_id,
        title=req.title,
        raw_content=req.content,
        category=req.category,
        trade_tags=req.trade_tags,
        hazard_tags=req.hazard_tags,
        language=req.language,
    )
    return {
        "status": "ok",
        "sections_created": len(docs),
        "document_ids": [d.id for d in docs],
    }


@router.post("/search")
async def search_documents(
    req: DocumentSearchRequest,
    db: Session = Depends(get_db),
):
    """Search documents by observation context (for testing retrieval)."""
    result = retrieve_relevant_documents(
        db=db,
        project_id=req.project_id,
        trade=req.trade,
        observation_text=req.observation_text,
        max_results=req.max_results,
    )
    return {
        "status": "ok",
        "document_count": len(result.document_ids),
        "document_ids": result.document_ids,
        "documents": result.documents,
        "formatted_context": result.formatted_context,
    }


@router.get("/list")
async def list_documents(
    project_id: int | None = None,
    category: str | None = None,
    db: Session = Depends(get_db),
):
    """List documents, optionally filtered by project and/or category."""
    query = db.query(SafetyDocument)
    if project_id is not None:
        query = query.filter(SafetyDocument.project_id == project_id)
    if category:
        query = query.filter(SafetyDocument.category == category)

    docs = query.order_by(SafetyDocument.created_at.desc()).limit(100).all()
    return {
        "status": "ok",
        "count": len(docs),
        "documents": [
            {
                "id": d.id,
                "title": d.title,
                "category": d.category,
                "section_label": d.section_label,
                "project_id": d.project_id,
                "source_attribution": d.source_attribution,
                "language": d.language,
                "content_preview": d.content[:200] if d.content else "",
            }
            for d in docs
        ],
    }
