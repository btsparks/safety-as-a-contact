"""Document layer — safety document ingestion, retrieval, and reference tracking."""

from backend.documents.retrieval import retrieve_relevant_documents, DocumentRetrievalResult
from backend.documents.ingestion import ingest_document

__all__ = [
    "retrieve_relevant_documents",
    "DocumentRetrievalResult",
    "ingest_document",
]
