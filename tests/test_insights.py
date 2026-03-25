"""Tests for the social feedback loop — observation insight generation."""

import pytest

from backend.documents.insights import generate_company_insights, generate_project_insights
from backend.models import Company, Observation, Project, SafetyDocument


@pytest.fixture
def company_and_project(db):
    """Create a test company and project with observations."""
    company = Company(name="Test Construction Co")
    db.add(company)
    db.commit()
    db.refresh(company)

    project = Project(name="Riverton Pump Station", company_id=company.id)
    db.add(project)
    db.commit()
    db.refresh(project)

    # Add observations across different hazard categories
    observations = [
        Observation(raw_text="Scaffold missing guardrail", project_id=project.id,
                    hazard_category="environmental", severity=4),
        Observation(raw_text="No harness on worker at edge", project_id=project.id,
                    hazard_category="environmental", severity=4),
        Observation(raw_text="Debris on walkway", project_id=project.id,
                    hazard_category="environmental", severity=2),
        Observation(raw_text="Grinder without guard", project_id=project.id,
                    hazard_category="equipment", severity=3),
        Observation(raw_text="Worker lifting heavy load", project_id=project.id,
                    hazard_category="ergonomic", severity=2),
    ]
    for obs in observations:
        db.add(obs)
    db.commit()

    return company, project


class TestProjectInsights:

    def test_generates_insight_document(self, db, company_and_project):
        _, project = company_and_project
        docs = generate_project_insights(db, project.id, period="monthly")
        assert len(docs) == 1
        assert docs[0].category == "observation_insight"
        assert "Riverton Pump Station" in docs[0].title

    def test_insight_content_has_counts(self, db, company_and_project):
        _, project = company_and_project
        docs = generate_project_insights(db, project.id, period="monthly")
        content = docs[0].content
        assert "Total observations: 5" in content
        assert "Environmental" in content

    def test_insight_has_attribution(self, db, company_and_project):
        _, project = company_and_project
        docs = generate_project_insights(db, project.id, period="monthly")
        assert "Observation Insights" in docs[0].source_attribution

    def test_replaces_old_insights(self, db, company_and_project):
        _, project = company_and_project
        # Generate twice
        generate_project_insights(db, project.id, period="weekly")
        generate_project_insights(db, project.id, period="weekly")

        # Should only have one weekly summary
        count = (
            db.query(SafetyDocument)
            .filter(
                SafetyDocument.project_id == project.id,
                SafetyDocument.category == "observation_insight",
                SafetyDocument.section_label == "weekly_summary",
            )
            .count()
        )
        assert count == 1

    def test_no_observations_returns_empty(self, db):
        company = Company(name="Empty Co")
        db.add(company)
        db.commit()
        db.refresh(company)
        project = Project(name="Empty Project", company_id=company.id)
        db.add(project)
        db.commit()
        db.refresh(project)

        docs = generate_project_insights(db, project.id, period="monthly")
        assert docs == []

    def test_nonexistent_project_returns_empty(self, db):
        docs = generate_project_insights(db, 99999, period="monthly")
        assert docs == []

    def test_insight_retrievable_by_document_search(self, db, company_and_project):
        """Insights should be findable by the document retrieval system."""
        _, project = company_and_project
        generate_project_insights(db, project.id, period="monthly")

        from backend.documents.retrieval import retrieve_relevant_documents
        # Search for keywords that appear in the insight content
        result = retrieve_relevant_documents(
            db=db,
            project_id=project.id,
            trade="laborer",
            observation_text="environmental observations equipment ergonomic",
        )
        # Should find the insight doc
        insight_ids = [
            d["id"] for d in result.documents
            if d["category"] == "observation_insight"
        ]
        assert len(insight_ids) >= 1


class TestCompanyInsights:

    def test_generates_company_wide_insights(self, db, company_and_project):
        company, _ = company_and_project
        docs = generate_company_insights(db, company.id, period="monthly")
        assert len(docs) == 1
        assert "Company" in docs[0].title
        assert docs[0].project_id is None  # Company-wide

    def test_cross_project_counts(self, db, company_and_project):
        company, project1 = company_and_project

        # Add a second project with observations
        project2 = Project(name="Second Site", company_id=company.id)
        db.add(project2)
        db.commit()
        db.refresh(project2)

        obs = Observation(
            raw_text="Trench without shoring",
            project_id=project2.id,
            hazard_category="environmental",
            severity=5,
        )
        db.add(obs)
        db.commit()

        docs = generate_company_insights(db, company.id, period="monthly")
        content = docs[0].content
        assert "2 projects" in content
        # Total should be 5 from first project + 1 from second = 6
        assert "Total observations across 2 projects: 6" in content

    def test_nonexistent_company_returns_empty(self, db):
        docs = generate_company_insights(db, 99999, period="monthly")
        assert docs == []
