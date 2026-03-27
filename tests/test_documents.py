"""Tests for the document layer — ingestion, retrieval, and API endpoints."""

import json

import pytest

from backend.documents.ingestion import ingest_document, VALID_CATEGORIES
from backend.documents.retrieval import (
    DocumentRetrievalResult,
    retrieve_relevant_documents,
    _extract_keywords,
    ES_TO_EN_SAFETY_TERMS,
)
from backend.models import Company, Project, SafetyDocument, DocumentReference


# --- Keyword extraction ---

class TestKeywordExtraction:

    def test_removes_stop_words(self):
        kws = _extract_keywords("the worker is on the roof")
        assert "the" not in kws
        assert "roof" in kws

    def test_removes_spanish_stop_words(self):
        kws = _extract_keywords("el trabajador esta en el techo")
        assert "techo" in kws
        assert "esta" not in kws

    def test_short_words_excluded(self):
        kws = _extract_keywords("a on it is to")
        assert kws == []

    def test_preserves_safety_terms(self):
        kws = _extract_keywords("scaffold fall protection harness")
        assert "scaffold" in kws
        assert "fall" in kws
        assert "harness" in kws


# --- Spanish → English keyword expansion ---

class TestSpanishKeywordExpansion:
    """Verify that Spanish safety terms produce English equivalents for retrieval."""

    def test_sierra_produces_saw(self):
        kws = _extract_keywords("La sierra")
        assert "sierra" in kws
        assert "saw" in kws

    def test_andamio_produces_scaffold(self):
        kws = _extract_keywords("andamio sin barandilla")
        assert "andamio" in kws
        assert "scaffold" in kws
        assert "guardrail" in kws

    def test_accented_proteccion_maps_to_protection(self):
        kws = _extract_keywords("protección contra caídas")
        assert "protection" in kws
        assert "fall" in kws

    def test_unaccented_proteccion_maps_to_protection(self):
        kws = _extract_keywords("proteccion contra caidas")
        assert "protection" in kws
        assert "fall" in kws

    def test_guarda_produces_guard(self):
        kws = _extract_keywords("No tiene la guarda puesta")
        assert "guarda" in kws
        assert "guard" in kws

    def test_full_spanish_observation_expands(self):
        kws = _extract_keywords("Mira hay rebar expuesto cerca del andamio")
        assert "rebar" in kws
        assert "scaffold" in kws

    def test_english_keywords_not_duplicated(self):
        """English terms should not be double-expanded."""
        kws = _extract_keywords("scaffold and harness check")
        assert kws.count("scaffold") == 1
        assert kws.count("harness") == 1

    def test_lookup_table_has_minimum_coverage(self):
        assert len(ES_TO_EN_SAFETY_TERMS) >= 50


class TestSpanishRetrieval:
    """Verify that Spanish observations retrieve English documents."""

    @pytest.fixture(autouse=True)
    def seed_english_docs(self, db):
        """Seed English-language safety documents."""
        self.saw_doc = ingest_document(
            db=db, project_id=None,
            title="Carpentry Safe Work Practices",
            raw_content=(
                "All portable circular saws must have functioning guards. "
                "Push sticks required for table saw operations."
            ),
            category="trade_reference",
            trade_tags=["carpenter", "all"],
            hazard_tags=["saw_operations"],
        )
        self.fall_doc = ingest_document(
            db=db, project_id=None,
            title="Fall Protection Standard",
            raw_content=(
                "Guardrails required on all open sides of scaffolds. "
                "Workers must use harnesses above 6 feet."
            ),
            category="site_safety_plan",
            trade_tags=["all"],
            hazard_tags=["fall_protection"],
        )

    def test_sierra_retrieves_saw_document(self, db):
        result = retrieve_relevant_documents(
            db=db, project_id=None, trade="carpenter",
            observation_text="La sierra no tiene guarda",
        )
        assert len(result.document_ids) > 0
        titles = [d["title"] for d in result.documents]
        assert any("Carpentry" in t or "saw" in t.lower() for t in titles), (
            f"Expected saw/carpentry doc, got: {titles}"
        )

    def test_andamio_retrieves_scaffold_document(self, db):
        result = retrieve_relevant_documents(
            db=db, project_id=None, trade="ironworker",
            observation_text="Andamio sin barandilla en el segundo piso",
        )
        assert len(result.document_ids) > 0
        titles = [d["title"] for d in result.documents]
        assert any("Fall" in t or "scaffold" in t.lower() for t in titles), (
            f"Expected fall/scaffold doc, got: {titles}"
        )

    def test_mixed_spanish_english_works(self, db):
        result = retrieve_relevant_documents(
            db=db, project_id=None, trade="carpenter",
            observation_text="El rebar esta expuesto near the scaffold",
        )
        assert len(result.document_ids) > 0


# --- Document ingestion ---

class TestIngestion:

    def test_ingest_single_section(self, db):
        docs = ingest_document(
            db=db,
            project_id=None,
            title="Test OSHA Standard",
            raw_content="Fall protection is required above 6 feet on all scaffolds.",
            category="osha_standard",
        )
        assert len(docs) == 1
        assert docs[0].title == "Test OSHA Standard"
        assert docs[0].category == "osha_standard"
        assert docs[0].project_id is None

    def test_ingest_multi_section_markdown(self, db):
        content = """## Fall Protection
Workers must use harnesses above 6 feet.

## Scaffolding
All scaffolds must have guardrails.

## Ladder Safety
Ladders must extend 3 feet above the landing."""
        docs = ingest_document(
            db=db,
            project_id=None,
            title="Safety Plan",
            raw_content=content,
            category="site_safety_plan",
        )
        assert len(docs) == 3
        assert docs[0].section_label == "Fall Protection"
        assert docs[1].section_label == "Scaffolding"
        assert docs[2].section_label == "Ladder Safety"

    def test_ingest_with_trade_tags(self, db):
        docs = ingest_document(
            db=db,
            project_id=None,
            title="Rigging Procedure",
            raw_content="Pre-lift checklist must be completed before every pick.",
            category="company_procedure",
            trade_tags=["ironworker", "operating_engineer"],
        )
        assert len(docs) == 1
        tags = json.loads(docs[0].trade_tags)
        assert "ironworker" in tags
        assert "operating_engineer" in tags

    def test_ingest_with_project(self, db):
        company = Company(name="Test Co")
        db.add(company)
        db.commit()
        db.refresh(company)

        project = Project(name="Pump Station", company_id=company.id)
        db.add(project)
        db.commit()
        db.refresh(project)

        docs = ingest_document(
            db=db,
            project_id=project.id,
            title="Pump Station Safety Plan",
            raw_content="Site-specific fall protection requirements.",
            category="site_safety_plan",
        )
        assert docs[0].project_id == project.id

    def test_ingest_invalid_category_raises(self, db):
        with pytest.raises(ValueError, match="Invalid category"):
            ingest_document(
                db=db,
                project_id=None,
                title="Bad Doc",
                raw_content="Content",
                category="not_a_real_category",
            )

    def test_source_attribution_generated(self, db):
        docs = ingest_document(
            db=db,
            project_id=None,
            title="Incident Report 2023-041",
            raw_content="Worker lacerated hand on unguarded grinder.",
            category="incident_report",
        )
        assert "Incident Report" in docs[0].source_attribution
        assert "2023-041" in docs[0].source_attribution

    def test_ingest_incident_report(self, db):
        docs = ingest_document(
            db=db,
            project_id=None,
            title="Incident #2014-037",
            raw_content="Hand laceration from unguarded angle grinder during metal prep.",
            category="incident_report",
            hazard_tags=["grinder", "laceration", "tool_guarding"],
        )
        assert len(docs) == 1
        assert docs[0].category == "incident_report"
        tags = json.loads(docs[0].hazard_tags)
        assert "grinder" in tags


# --- Document retrieval ---

class TestRetrieval:

    @pytest.fixture(autouse=True)
    def seed_documents(self, db):
        """Seed some test documents for retrieval tests."""
        self.docs = ingest_document(
            db=db,
            project_id=None,
            title="Site Safety Plan",
            raw_content=(
                "## Fall Protection\n"
                "Workers must wear harnesses above 6 feet on all scaffolds.\n"
                "Guardrails required on all open-sided platforms.\n\n"
                "## Housekeeping\n"
                "Work areas must be kept clean and free of debris.\n"
                "Materials must be properly stored."
            ),
            category="site_safety_plan",
            trade_tags=["all"],
        )
        self.incident_doc = ingest_document(
            db=db,
            project_id=None,
            title="Incident #2023-041",
            raw_content="Worker lacerated hand on unguarded angle grinder during metal prep work.",
            category="incident_report",
            trade_tags=["all"],
            hazard_tags=["grinder", "laceration"],
        )

    def test_retrieves_matching_documents(self, db):
        result = retrieve_relevant_documents(
            db=db,
            project_id=None,
            trade="carpenter",
            observation_text="scaffold without guardrail",
        )
        assert len(result.document_ids) > 0
        assert result.formatted_context != ""

    def test_returns_empty_when_no_match(self, db):
        result = retrieve_relevant_documents(
            db=db,
            project_id=None,
            trade="carpenter",
            observation_text="xyzzy foobar blargh",
        )
        assert len(result.document_ids) == 0
        assert result.formatted_context == ""

    def test_incident_reports_prioritized(self, db):
        result = retrieve_relevant_documents(
            db=db,
            project_id=None,
            trade="laborer",
            observation_text="grinder on table without guard",
        )
        # Incident report should appear first due to category priority
        assert len(result.document_ids) > 0
        first_doc = result.documents[0]
        assert first_doc["category"] == "incident_report"

    def test_formatted_context_has_attribution(self, db):
        result = retrieve_relevant_documents(
            db=db,
            project_id=None,
            trade="ironworker",
            observation_text="fall protection harness scaffold",
        )
        assert "[Source:" in result.formatted_context

    def test_max_results_respected(self, db):
        result = retrieve_relevant_documents(
            db=db,
            project_id=None,
            trade="general",
            observation_text="scaffold guardrail fall harness grinder",
            max_results=1,
        )
        assert len(result.document_ids) <= 1

    def test_empty_observation_returns_empty(self, db):
        result = retrieve_relevant_documents(
            db=db,
            project_id=None,
            trade="general",
            observation_text="",
        )
        assert len(result.document_ids) == 0


# --- API endpoint tests ---

class TestDocumentAPI:

    def test_upload_endpoint(self, client, db):
        resp = client.post("/api/documents/upload", json={
            "title": "API Test Document",
            "content": "Fall protection required on all elevated work.",
            "category": "company_procedure",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["sections_created"] >= 1

    def test_search_endpoint(self, client, db):
        # Upload first
        client.post("/api/documents/upload", json={
            "title": "Fall Protection Standard",
            "content": "Workers must use harnesses above 6 feet.",
            "category": "osha_standard",
        })
        # Search
        resp = client.post("/api/documents/search", json={
            "trade": "ironworker",
            "observation_text": "harness fall protection",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["document_count"] >= 1

    def test_list_endpoint(self, client, db):
        client.post("/api/documents/upload", json={
            "title": "Test Doc",
            "content": "Content here.",
            "category": "trade_reference",
        })
        resp = client.get("/api/documents/list")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1

    def test_list_filtered_by_category(self, client, db):
        client.post("/api/documents/upload", json={
            "title": "Incident X",
            "content": "Incident details here.",
            "category": "incident_report",
        })
        resp = client.get("/api/documents/list?category=incident_report")
        assert resp.status_code == 200
        data = resp.json()
        for doc in data["documents"]:
            assert doc["category"] == "incident_report"
