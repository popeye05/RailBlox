# Development handoff

The application is split at the API boundary. Backend domain work belongs in `backend/app`; React views live in `frontend/src`.

The authenticated prototype adds `security.py` (Supabase verification/roles), `ai.py` (Responses API with structured evidence checks), `learning.py` (retrospective ridge-regression evaluation) and `platform_api.py` (AI endpoints and persisted automation). UI integration is in `Auth.tsx` and `AITools.tsx`. Read [deployment and credential setup](deployment.md). Production uses one API process and one division per database; the private PostgreSQL schema is separate from local SQLite. Do not run multiple workers against the in-process solve queue.

SPEC 2 implementation lives in `intelligence_models.py`, `intelligence.py`, `intelligence_api.py`, and the shared `protection.py` constraint union. Frontend views are in `DecisionWorkspace.tsx` with explicit API types in `intelligenceTypes.ts`. Read [the SPEC 2 handoff](spec2-implementation.md) before modifying policy, evidence, or review behavior. Do not label the local policy/statistical baselines as trained production AI.

Asset uptime decision support lives in `availability.py`, with snapshot health fixtures in `fixtures.py`, API endpoints in `main.py`, and the officer-facing view in `AvailabilityWorkspace.tsx`. The availability model is deterministic and explainable; it must remain separate from hard safety validation and must continue to display its synthetic/advisory boundary.

Useful independent contributions:

- Review the synthetic task names and explanatory text in `fixtures.py` and the five-minute demo script. Keep the documented A/B/C durations and constraints unchanged.
- Expand the presentation dataset with additional realistic-looking but explicitly synthetic task/resource cases. Add a meaningful rule test whenever changing feasibility behavior.
- Run Docker Compose on a Docker-capable machine and record PostgreSQL verification.
- Refactor `frontend/src/App.tsx` into route modules as the UI grows; retain the shared query/URL context and backend operations.

Run backend tests before changing the solver or persistence rules. Run the browser suite for interaction changes. Browser testing uses separate ports 8001/5174 and a uniquely named SQLite database, so it does not approve, import into or otherwise alter the native demo database.

The project repository is https://github.com/popeye05/RailBlox. Source, lockfiles, tests and deployment configuration are versioned; local credentials, databases, dependencies and generated artifacts are excluded. GitHub Actions verifies pushes and pull requests. Hosting deployment remains a separate step.
