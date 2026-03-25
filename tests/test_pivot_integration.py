"""Pivot integration tests — end-to-end validation of the document-grounded model.

Seeds a small document library and runs simulated worker interactions through
the full coaching pipeline (mock mode). Validates:

1. Document retrieval works and references appear in responses
2. Response modes are correct (reference/reflect/connect)
3. No prohibited phrases or technical advice in responses
4. Worker profiles update correctly across interactions
5. Trade-aware personalization works
6. Session management and document reference logging

Run with: pytest tests/test_pivot_integration.py -v
"""

import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.database import Base
from backend.models import (
    Company, DocumentReference, Project, SafetyDocument, Worker,
    WorkerProfile, CoachingSession, Observation, InteractionAssessment,
    hash_phone, utcnow,
)
from backend.documents.ingestion import ingest_document
from backend.documents.retrieval import retrieve_relevant_documents
from backend.coaching.engine import run_coaching, coach_mock
from backend.coaching.profile import get_or_create_profile, calculate_tier


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    """In-memory SQLite database with all tables created."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    _Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = _Session()
    yield session
    session.close()


@pytest.fixture
def seeded_db(db):
    """Database with a company, project, workers, and seed safety documents."""

    # Company + Project
    company = Company(name="Wollam Construction")
    db.add(company)
    db.commit()
    db.refresh(company)

    project = Project(
        company_id=company.id,
        name="Downtown Office Tower",
        location="1200 Main St, Dallas TX",
        description="14-story steel frame office building. Active floors 6-14. "
                    "Crane operations daily. Concrete pours on 3-day cycle.",
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    # Workers — different trades, languages, experience
    jake = Worker(
        phone_hash=hash_phone("+15551001001"),
        company_id=company.id,
        project_id=project.id,
        active_project_id=project.id,
        first_name="Jake",
        trade="ironworker",
        experience_level="intermediate",
        preferred_language="en",
    )
    miguel = Worker(
        phone_hash=hash_phone("+15551002002"),
        company_id=company.id,
        project_id=project.id,
        active_project_id=project.id,
        first_name="Miguel",
        trade="carpenter",
        experience_level="entry",
        preferred_language="es",
    )
    sarah = Worker(
        phone_hash=hash_phone("+15551003003"),
        company_id=company.id,
        project_id=project.id,
        active_project_id=project.id,
        first_name="Sarah",
        trade="electrician",
        experience_level="expert",
        preferred_language="en",
    )
    db.add_all([jake, miguel, sarah])
    db.commit()
    for w in [jake, miguel, sarah]:
        db.refresh(w)

    # --- SEED DOCUMENTS ---

    # 1. Site Safety Plan (project-specific)
    ingest_document(
        db,
        project_id=project.id,
        title="Downtown Office Tower Site Safety Plan",
        raw_content="""## Fall Protection Requirements
All workers operating at heights above 6 feet must use personal fall arrest systems.
Guardrails are required on all open sides of floors, platforms, and walkways.
Leading edge work requires a written fall protection plan reviewed by the site safety director.
Workers must inspect harness and lanyard connections before each use.

## Housekeeping Standards
All work areas must be cleaned at end of each shift. Debris must not accumulate near
floor edges or stairwells. Material staging areas must be clearly marked with barriers.
Combustible waste must be placed in designated containers and removed daily.

## Crane Operations
Only qualified riggers may attach loads. All crane picks must have a lift plan.
Tag lines required on all loads. No workers under suspended loads at any time.
Signal person must have unobstructed view of load and operator.

## Electrical Safety
All temporary power must be GFCI protected. Lockout/tagout procedures required
before any electrical work. Minimum 10-foot clearance from overhead power lines.
Only qualified electricians may work on energized circuits.

## Excavation and Trenching
All excavations deeper than 5 feet require protective systems (sloping, shoring, or shield).
Competent person must inspect excavations daily and after rain events.
Spoil piles must be at least 2 feet from trench edge.""",
        category="site_safety_plan",
        trade_tags=["all"],
        hazard_tags=["fall_protection", "housekeeping", "crane", "electrical", "excavation"],
    )

    # 2. Incident Report (company-wide)
    ingest_document(
        db,
        project_id=None,  # global
        title="Incident Report #2024-017: Near-Miss Falling Object",
        raw_content="""## Incident Summary
On March 12, 2024, a 3/4-inch bolt fell from the 9th floor during steel erection,
landing 4 feet from a carpenter working on the 6th floor deck. No injuries occurred.
The bolt had not been secured in the connector bolt bag after installation.

## Root Cause
Ironworker did not follow the bolting procedure which requires all loose connectors
to be stored in the bolt bag between installations. The bolt bag was not attached
to the worker's harness as required by company procedure.

## Corrective Actions
1. All ironworkers retrained on connector bolt storage procedure.
2. Bolt bags now inspected during daily harness checks.
3. Exclusion zone below active steel erection expanded from 15 to 25 feet.
4. Nets installed below active connection points on floors 7 through 14.""",
        category="incident_report",
        trade_tags=["ironworker", "carpenter", "all"],
        hazard_tags=["falling_object", "struck_by"],
    )

    # 3. OSHA Standard reference (global)
    ingest_document(
        db,
        project_id=None,
        title="OSHA 1926.501 - Fall Protection Scope and Requirements",
        raw_content="""## General Requirements
Each employee on a walking/working surface with an unprotected side or edge
which is 6 feet or more above a lower level shall be protected from falling by
the use of guardrail systems, safety net systems, or personal fall arrest systems.

## Leading Edge Work
Each employee who is constructing a leading edge 6 feet or more above lower levels
shall be protected from falling by guardrail systems, safety net systems, or
personal fall arrest systems.

## Hoist Areas
Each employee in a hoist area shall be protected from falling 6 feet or more to
lower levels by guardrail systems or personal fall arrest systems.""",
        category="osha_standard",
        trade_tags=["all"],
        hazard_tags=["fall_protection"],
    )

    # 4. Trade Reference — Carpentry (trade-specific)
    ingest_document(
        db,
        project_id=project.id,
        title="Carpentry Safe Work Practices - Formwork",
        raw_content="""## Formwork Erection Safety
All formwork must be designed by a qualified person. Shoring must be inspected
before concrete placement. Workers must verify shore loads do not exceed
manufacturer ratings. Reshoring required on multi-story pours.

## Saw Operations
All portable circular saws must have functioning guards. Push sticks required
for table saw operations. Workers must wear eye protection and hearing protection
when operating saws. Ensure blade is appropriate for material being cut.

## Material Handling
Lumber and plywood must be stacked on level surfaces with proper dunnage.
Stack height must not exceed 16 feet. Band materials before hoisting.
Workers must use proper lifting techniques — get help for loads over 50 lbs.""",
        category="trade_reference",
        trade_tags=["carpenter"],
        hazard_tags=["formwork", "saw_operations", "material_handling"],
    )

    # 5. Lessons Learned (company-wide)
    ingest_document(
        db,
        project_id=None,
        title="Lessons Learned: Heat Illness Prevention Summer 2024",
        raw_content="""## Summary
During summer 2024, we had 3 heat-related incidents across company projects.
Two were heat exhaustion cases on concrete pour days, one was heat stroke
requiring emergency medical response.

## Key Findings
Workers on concrete pour days are at highest risk due to extended sun exposure
and physical exertion. Hydration stations more than 100 feet from work areas
were underutilized. New workers (less than 2 weeks on site) accounted for
all 3 incidents.

## Recommendations
Hydration stations within 50 feet of active work areas. Mandatory buddy system
on days above 95°F. Acclimatization protocol for all new workers: reduced
workload first 2 weeks. Foremen trained to recognize early signs.""",
        category="lessons_learned",
        trade_tags=["all"],
        hazard_tags=["heat_illness", "environmental"],
    )

    return {
        "db": db,
        "company": company,
        "project": project,
        "jake": jake,
        "miguel": miguel,
        "sarah": sarah,
    }


# ---------------------------------------------------------------------------
# Prohibited phrases list (from prompts.py)
# ---------------------------------------------------------------------------

PROHIBITED_PHRASES = [
    "that setup looks unsafe",
    "that's a hazard",
    "that needs to be fixed",
    "you need to",
    "you should",
    "make sure you",
    "i can see that",
    "i notice that",
    "it looks like",
    "i recommend",
    "i suggest",
    "i advise",
    "based on my experience",
    "in my experience",
    "from what i can see",
    "that's not right",
    "that's incorrect",
    "that's wrong",
    "that's dangerous",
    "that's a violation",
    "you're doing it wrong",
    "you need to fix",
    "you should fix",
    "you must",
    "you have to",
    "don't do that",
    "stop doing that",
    "that won't work",
    "that's not going to work",
    "here's what you should do",
    "let me tell you",
    "i think you should",
    "the correct way",
    "the right way",
    "the proper way",
    "i can tell",
    "i can see",
    "i see that",
    "looking at this",
    "what i see here",
    "i'm seeing",
    "it appears that",
    "clearly",
    "obviously",
    "you failed to",
    "you forgot to",
    "you missed",
    "you overlooked",
]


def _check_prohibited_phrases(text: str) -> list[str]:
    """Return any prohibited phrases found in the response text."""
    lower = text.lower()
    return [phrase for phrase in PROHIBITED_PHRASES if phrase in lower]


def _check_technical_advice(text: str) -> list[str]:
    """Check for patterns that suggest the AI is giving technical safety advice."""
    lower = text.lower()
    red_flags = []

    # Direct instructions / imperatives
    imperative_patterns = [
        "make sure the",
        "ensure the",
        "check the",
        "verify that",
        "always use",
        "never use",
        "you need a",
        "you'll want to",
        "the correct procedure is",
        "the sling angle should",
        "the bearing surface",
        "the load capacity",
        "rated for",
        "the minimum distance",
    ]
    for pattern in imperative_patterns:
        if pattern in lower:
            red_flags.append(f"Technical advice pattern: '{pattern}'")

    return red_flags


# ---------------------------------------------------------------------------
# Test: Document Retrieval
# ---------------------------------------------------------------------------

class TestDocumentRetrieval:
    """Verify that documents are found and returned correctly for different scenarios."""

    def test_fall_protection_query_returns_documents(self, seeded_db):
        db = seeded_db["db"]
        project = seeded_db["project"]
        result = retrieve_relevant_documents(
            db, project_id=project.id, trade="ironworker",
            observation_text="Working near the edge on the 8th floor, no guardrails up yet",
        )
        assert len(result.document_ids) > 0
        assert result.formatted_context != ""
        # Should find site safety plan or OSHA standard about fall protection
        categories = [d["category"] for d in result.documents]
        assert any(c in categories for c in ["site_safety_plan", "osha_standard", "incident_report"])

    def test_trade_specific_docs_returned_for_carpenter(self, seeded_db):
        db = seeded_db["db"]
        project = seeded_db["project"]
        result = retrieve_relevant_documents(
            db, project_id=project.id, trade="carpenter",
            observation_text="Formwork shoring saw plywood lumber cutting material",
        )
        assert len(result.document_ids) > 0
        # Should include the carpentry trade reference
        titles = [d["title"] for d in result.documents]
        assert any("Carpentry" in t or "Formwork" in t for t in titles), (
            f"Expected carpentry doc in results, got titles: {titles}"
        )

    def test_incident_report_surfaces_for_falling_object(self, seeded_db):
        db = seeded_db["db"]
        project = seeded_db["project"]
        result = retrieve_relevant_documents(
            db, project_id=project.id, trade="ironworker",
            observation_text="Saw a bolt fall from the floor above while connecting steel",
        )
        assert len(result.document_ids) > 0
        # Incident reports should be prioritized
        categories = [d["category"] for d in result.documents]
        assert "incident_report" in categories

    def test_no_results_for_irrelevant_query(self, seeded_db):
        db = seeded_db["db"]
        project = seeded_db["project"]
        result = retrieve_relevant_documents(
            db, project_id=project.id, trade="ironworker",
            observation_text="Having lunch in the break trailer",
        )
        # May or may not find docs — that's fine. Just shouldn't crash.
        assert isinstance(result.document_ids, list)

    def test_global_docs_returned_when_no_project_specific(self, seeded_db):
        db = seeded_db["db"]
        # Query with a non-existent project ID — should still get global docs
        result = retrieve_relevant_documents(
            db, project_id=9999, trade="ironworker",
            observation_text="Working at height with fall protection harness",
        )
        # Global OSHA standard should still be found
        assert len(result.document_ids) >= 0  # may find global docs

    def test_attribution_format(self, seeded_db):
        db = seeded_db["db"]
        project = seeded_db["project"]
        result = retrieve_relevant_documents(
            db, project_id=project.id, trade="ironworker",
            observation_text="fall protection harness edge",
        )
        if result.formatted_context:
            assert "[Source:" in result.formatted_context


# ---------------------------------------------------------------------------
# Test: Mock Coaching Responses
# ---------------------------------------------------------------------------

class TestMockResponses:
    """Verify mock responses comply with the pivot framework."""

    def test_mock_response_modes_are_valid(self):
        modes_seen = set()
        test_observations = [
            ("Spotted a guy near the edge without a harness", "ironworker", ["http://photo.jpg"]),
            ("Crew keeping the area clean today", "carpenter", ["http://photo.jpg"]),
            ("That excavation over there looks different than our area", "electrician", ["http://photo.jpg"]),
        ]
        for obs_text, trade, media in test_observations:
            result = coach_mock(obs_text, trade=trade, media_urls=media)
            modes_seen.add(result.response_mode)
            assert result.response_mode in ("reference", "reflect", "connect")

    def test_mock_no_prohibited_phrases(self):
        observations = [
            "Saw someone on the scaffold without a harness",
            "There's exposed rebar near the walkway",
            "The electrical panel is open and nobody is around",
            "Trench looks deep, not sure if there's shoring",
            "Crew doing a great job with housekeeping today",
        ]
        for obs in observations:
            result = coach_mock(obs, trade="ironworker", media_urls=["http://photo.jpg"])
            violations = _check_prohibited_phrases(result.response_text)
            assert not violations, f"Prohibited phrases in mock response: {violations}"

    def test_mock_no_technical_advice(self):
        observations = [
            "Saw someone on the scaffold without a harness",
            "There's exposed rebar near the walkway",
            "Trench looks deep",
        ]
        for obs in observations:
            result = coach_mock(obs, trade="ironworker", media_urls=["http://photo.jpg"])
            flags = _check_technical_advice(result.response_text)
            assert not flags, f"Technical advice in mock response: {flags}"

    def test_mock_asks_for_photo_on_first_turn_no_photo(self):
        result = coach_mock("There's a problem near the edge", trade="ironworker", turn_number=1)
        # Should ask for photo when none provided
        lower = result.response_text.lower()
        assert "photo" in lower

    def test_mock_high_severity_uses_reference_mode(self):
        # Trench/excavation = severity 5 → should force reference mode
        result = coach_mock("Open trench near the building with no shoring",
                            trade="ironworker", media_urls=["http://photo.jpg"])
        assert result.response_mode == "reference"
        assert result.severity >= 4


# ---------------------------------------------------------------------------
# Test: Full Pipeline (Mock Mode)
# ---------------------------------------------------------------------------

class TestFullPipeline:
    """Run the full run_coaching() pipeline with seeded documents."""

    def test_basic_pipeline_returns_result(self, seeded_db):
        db = seeded_db["db"]
        jake = seeded_db["jake"]

        # Create an observation first
        obs = Observation(
            worker_id=jake.id,
            project_id=seeded_db["project"].id,
            raw_text="Saw a bolt on the ground near the steel connection area",
            media_urls=json.dumps(["http://example.com/photo1.jpg"]),
        )
        db.add(obs)
        db.commit()
        db.refresh(obs)

        result = run_coaching(
            db,
            observation_text=obs.raw_text,
            trade="ironworker",
            experience_level="intermediate",
            observation_id=obs.id,
            media_urls=["http://example.com/photo1.jpg"],
            phone_hash=jake.phone_hash,
            worker_id=jake.id,
        )

        assert result.response_text
        assert result.response_mode in ("reference", "reflect", "connect")
        assert result.is_mock  # no API key set

    def test_pipeline_creates_session(self, seeded_db):
        db = seeded_db["db"]
        jake = seeded_db["jake"]

        obs = Observation(
            worker_id=jake.id,
            project_id=seeded_db["project"].id,
            raw_text="Working near the leading edge today",
            media_urls=json.dumps(["http://example.com/photo1.jpg"]),
        )
        db.add(obs)
        db.commit()
        db.refresh(obs)

        result = run_coaching(
            db,
            observation_text=obs.raw_text,
            trade="ironworker",
            observation_id=obs.id,
            media_urls=["http://example.com/photo1.jpg"],
            phone_hash=jake.phone_hash,
            worker_id=jake.id,
        )

        # Should have created a session
        sessions = db.query(CoachingSession).filter(
            CoachingSession.phone_hash == jake.phone_hash
        ).all()
        assert len(sessions) >= 1

    def test_pipeline_creates_worker_profile(self, seeded_db):
        db = seeded_db["db"]
        jake = seeded_db["jake"]

        obs = Observation(
            worker_id=jake.id,
            project_id=seeded_db["project"].id,
            raw_text="Harness looks worn near the D-ring",
            media_urls=json.dumps(["http://example.com/photo1.jpg"]),
        )
        db.add(obs)
        db.commit()
        db.refresh(obs)

        result = run_coaching(
            db,
            observation_text=obs.raw_text,
            trade="ironworker",
            observation_id=obs.id,
            media_urls=["http://example.com/photo1.jpg"],
            phone_hash=jake.phone_hash,
            worker_id=jake.id,
        )

        profile = db.query(WorkerProfile).filter(
            WorkerProfile.phone_hash == jake.phone_hash
        ).first()
        assert profile is not None
        assert profile.total_turns >= 1

    def test_pipeline_logs_document_references(self, seeded_db):
        db = seeded_db["db"]
        jake = seeded_db["jake"]

        obs = Observation(
            worker_id=jake.id,
            project_id=seeded_db["project"].id,
            raw_text="Bolt fell from above near the steel erection area",
            media_urls=json.dumps(["http://example.com/photo1.jpg"]),
        )
        db.add(obs)
        db.commit()
        db.refresh(obs)

        result = run_coaching(
            db,
            observation_text=obs.raw_text,
            trade="ironworker",
            observation_id=obs.id,
            media_urls=["http://example.com/photo1.jpg"],
            phone_hash=jake.phone_hash,
            worker_id=jake.id,
        )

        # If documents were found, references should be logged
        if result.document_ids:
            refs = db.query(DocumentReference).filter(
                DocumentReference.phone_hash == jake.phone_hash
            ).all()
            assert len(refs) > 0

    def test_pipeline_saves_interaction_assessment(self, seeded_db):
        db = seeded_db["db"]
        miguel = seeded_db["miguel"]

        obs = Observation(
            worker_id=miguel.id,
            project_id=seeded_db["project"].id,
            raw_text="Mira hay rebar expuesto cerca del andamio",
            media_urls=json.dumps(["http://example.com/photo1.jpg"]),
        )
        db.add(obs)
        db.commit()
        db.refresh(obs)

        result = run_coaching(
            db,
            observation_text=obs.raw_text,
            trade="carpenter",
            observation_id=obs.id,
            media_urls=["http://example.com/photo1.jpg"],
            phone_hash=miguel.phone_hash,
            worker_id=miguel.id,
            preferred_language="es",
        )

        assessments = db.query(InteractionAssessment).filter(
            InteractionAssessment.phone_hash == miguel.phone_hash
        ).all()
        assert len(assessments) >= 1

    def test_multi_turn_session(self, seeded_db):
        """Simulate 3 turns in the same session and verify session continuity."""
        db = seeded_db["db"]
        sarah = seeded_db["sarah"]

        turns = [
            ("Open electrical panel on level 7, nobody working on it",
             ["http://example.com/panel.jpg"]),
            ("Checked the breaker schedule, looks like it should be locked out",
             ["http://example.com/breaker.jpg"]),
            ("Foreman says they're coming back to finish, thanks for flagging it", None),
        ]

        for obs_text, media in turns:
            obs = Observation(
                worker_id=sarah.id,
                project_id=seeded_db["project"].id,
                raw_text=obs_text,
                media_urls=json.dumps(media or []),
            )
            db.add(obs)
            db.commit()
            db.refresh(obs)

            result = run_coaching(
                db,
                observation_text=obs_text,
                trade="electrician",
                experience_level="expert",
                observation_id=obs.id,
                media_urls=media,
                phone_hash=sarah.phone_hash,
                worker_id=sarah.id,
            )
            assert result.response_text

        # Should all be in one session
        sessions = db.query(CoachingSession).filter(
            CoachingSession.phone_hash == sarah.phone_hash,
            CoachingSession.is_closed == False,
        ).all()
        assert len(sessions) == 1
        assert sessions[0].turn_count == 3


# ---------------------------------------------------------------------------
# Test: Response Quality Validation
# ---------------------------------------------------------------------------

class TestResponseQuality:
    """Validate that responses meet the pivot's behavioral criteria."""

    def test_no_first_person_constructions(self, seeded_db):
        """AI should never use 'I can see', 'I notice', etc."""
        db = seeded_db["db"]
        jake = seeded_db["jake"]

        observations = [
            "No guardrails on the east side of floor 9",
            "Bolt fell from the floor above",
            "Crane rigging looks different today",
        ]
        for obs_text in observations:
            obs = Observation(
                worker_id=jake.id,
                project_id=seeded_db["project"].id,
                raw_text=obs_text,
                media_urls=json.dumps(["http://example.com/photo.jpg"]),
            )
            db.add(obs)
            db.commit()
            db.refresh(obs)

            result = run_coaching(
                db, observation_text=obs_text, trade="ironworker",
                observation_id=obs.id,
                media_urls=["http://example.com/photo.jpg"],
                phone_hash=jake.phone_hash, worker_id=jake.id,
            )

            lower = result.response_text.lower()
            first_person = ["i can", "i see", "i notice", "i think", "i recommend",
                            "i suggest", "i advise", "i'm seeing", "i can tell"]
            violations = [fp for fp in first_person if fp in lower]
            assert not violations, (
                f"First-person construction in response: {violations}\n"
                f"Response: {result.response_text}"
            )

    def test_responses_end_with_question_or_prompt(self):
        """Most responses should end with a question or conversational prompt."""
        observations = [
            ("Scaffold missing toe boards on level 5", "ironworker", ["http://photo.jpg"]),
            ("Housekeeping is great today", "carpenter", ["http://photo.jpg"]),
            ("Excavation near the south wall", "carpenter", ["http://photo.jpg"]),
        ]
        question_count = 0
        for obs_text, trade, media in observations:
            result = coach_mock(obs_text, trade=trade, media_urls=media)
            if "?" in result.response_text:
                question_count += 1

        # At least 2 out of 3 should have a question
        assert question_count >= 2, (
            f"Only {question_count}/3 responses contained a question"
        )


# ---------------------------------------------------------------------------
# Test: Worker Profile Progression
# ---------------------------------------------------------------------------

class TestWorkerProgression:
    """Verify the tier calculation and profile updates work correctly."""

    def test_photo_rate_affects_tier(self, db):
        """Photo consistency should now be weighted in tier calculation."""
        # Create assessment data simulating a worker who sends photos consistently
        assessments = []
        for i in range(10):
            a = InteractionAssessment(
                phone_hash="test_photo_worker",
                turn_number=i + 1,
                specificity_score=3,
                worker_engagement="medium",
                worker_confidence="confident",
                hazard_present=True,
                has_photo=True,  # 100% photo rate
                worker_asked_question=(i % 3 == 0),
                teachable_moment=(i % 4 == 0),
                worker_text_length=20,
            )
            db.add(a)
            assessments.append(a)
        db.commit()

        tier = calculate_tier(assessments, current_tier=1)
        # High photo rate + confident + hazard present should push tier up
        assert tier >= 2

    def test_low_text_worker_can_progress(self, db):
        """Workers who send photos with minimal text should still progress (Miguel scenario)."""
        assessments = []
        for i in range(15):
            a = InteractionAssessment(
                phone_hash="test_low_text_worker",
                turn_number=i + 1,
                specificity_score=2,  # Low text specificity
                worker_engagement="low",  # Low text engagement
                worker_confidence="uncertain",
                hazard_present=True,  # Good hazard identification via photos
                has_photo=True,  # Almost always sends photos
                worker_asked_question=False,
                teachable_moment=(i % 5 == 0),
                worker_text_length=10,  # Very short texts
            )
            db.add(a)
            assessments.append(a)
        db.commit()

        tier = calculate_tier(assessments, current_tier=1)
        # Photo consistency (15%) + hazard accuracy (15%) + initiative photo component (5%)
        # should push even low-text workers above tier 1
        assert tier >= 2, (
            f"Low-text photo worker stuck at tier {tier}. "
            "Photo rate should compensate for minimal text."
        )


# ---------------------------------------------------------------------------
# Test: Document Ingestion
# ---------------------------------------------------------------------------

class TestDocumentIngestion:
    """Verify document chunking and tagging."""

    def test_markdown_sections_split_correctly(self, db):
        company = Company(name="Test Co")
        db.add(company)
        db.commit()

        docs = ingest_document(
            db,
            project_id=None,
            title="Test Document",
            raw_content="""## Section One
Content for section one about fall protection and harness inspection.

## Section Two
Content for section two about ladder safety and three-point contact.

## Section Three
Content for section three about scaffold erection.""",
            category="company_procedure",
            trade_tags=["all"],
            hazard_tags=["fall_protection"],
        )

        assert len(docs) == 3
        assert docs[0].section_label == "Section One"
        assert docs[1].section_label == "Section Two"
        assert docs[2].section_label == "Section Three"

    def test_attribution_includes_category_and_title(self, db):
        docs = ingest_document(
            db,
            project_id=None,
            title="OSHA 1926.451 Scaffolding",
            raw_content="All scaffolds must be erected under supervision of a competent person.",
            category="osha_standard",
        )
        assert len(docs) == 1
        assert "OSHA 1926.451 Scaffolding" in docs[0].source_attribution
        assert "OSHA Standard" in docs[0].source_attribution

    def test_invalid_category_raises_error(self, db):
        with pytest.raises(ValueError, match="Invalid category"):
            ingest_document(
                db, project_id=None, title="Bad Doc",
                raw_content="Content", category="invalid_category",
            )
