---
paths:
  - "src/models/**/*.py"
  - "migrations/**/*.py"
---

# Database and Models Rules

Rules for database models and migrations:

## Table Design and Constraints
- worker_id in observations table MUST be nullable (anonymous reporting)
- consent_records are immutable — never update, only insert new records
- consent_records must have unique constraint on (phone_number, consent_type, is_active)
- Foreign key constraints must be explicit
- Phone numbers stored in E.164 format, hashed for anonymous workers
- All timestamps in UTC, convert to local time only at display/sending layer

## Data Management Patterns
- Soft delete pattern for all user-facing data (add deleted_at column, never DROP)
- NEVER delete consent records — use revoked_at timestamp for soft delete
- engagement_metrics calculated on a rolling 30-day window
- All JSON columns (standards_config, ai_analysis) must have a defined schema

## Indexing Strategy
- Index phone_number and created_at on high-volume tables (observations, message_log)
- Consider partial indexes for active records (WHERE deleted_at IS NULL)

## Migrations
- Migration files must be reversible (include downgrade)
- Include data validation steps in migrations
- Document any schema changes that affect API contracts
