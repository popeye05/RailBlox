# SPEC 3 — Production RBAC, Administration and Operational Readiness

## Handoff

This document is the next implementation brief for Astra. RailBLOX is a React + FastAPI + OR-Tools prototype with Supabase Auth. The current build has four effective roles, a profile page, signup profile fields, an Admin user-access page, server-side access checks, and Officer-only plan validation/benchmark endpoints. Continue from the existing code; do not replace working authentication or the solver.

## 1. Account and profile experience

Improve the account control in the authenticated header so it is clearly visible on desktop and mobile, has an active state, and opens the profile page without a full reload. The profile page must show the authenticated user's email, full name, assigned division, effective role, account identifier, password actions and sign-out.

Signup currently collects full name, date of birth and a requested role. Store those as user profile metadata. The requested role is only a request and must never grant access. The backend must continue to trust only administrator-controlled `app_metadata.railblox_role` and `app_metadata.railblox_division`.

Treat date of birth as sensitive. Keep it out of audit records and other users' listings. Confirm with the operational owner whether it is required before production; if it is not required, remove it from the production signup form.

## 2. Admin user access

Keep the Admin → User access page at `/admin/users`. It must:

- List Supabase users with email, name, confirmation state, requested role, assigned role and assigned division.
- Assign `viewer`, `planner`, `officer` or `admin`.
- Remove RailBLOX access without deleting the Supabase account.
- Prevent an administrator from removing their own final admin access.
- Record every access change in the append-only audit history.
- Show a clear configuration message when the backend-only Supabase Admin key is absent.

The backend Admin API requires `SUPABASE_SERVICE_ROLE_KEY` (or the current Supabase secret key) in the backend secret manager only. Never send it to the browser, put it in a `VITE_` variable or commit it. Prefer administrator invitations and disable public signup for a controlled railway deployment.

## 3. Role matrix and interface behavior

All users share the same application shell and see records for the configured division. Their effective role controls actions and data operations:

| Role | Allowed behavior |
|---|---|
| Viewer | Read schedules, evidence, recommendations, results and reports; export read-only records. |
| Planner | Maintain work inputs, import and map evidence, generate/revise proposed plans, run local analysis, prepare report drafts and request optional AI drafts. |
| Officer | All Planner read access plus formal plan validation, benchmark testing, recommendation approval/rejection, commitment finalization, report review and actual outcome recording. |
| Admin | All Officer access plus user access management, automation configuration and audit review. |

Implement the matrix twice:

1. The FastAPI middleware and route handlers must reject unauthorized calls even if a request is forged.
2. The React interface must hide or disable every mutating action that the current role cannot perform and explain which role is required.

Keep exports and inspection actions available to Viewers. Do not hide evidence needed to understand why an action is restricted.

## 4. Officer checks

Officer-level API actions must include:

- `POST /api/plans/{id}/validate`
- `POST /api/benchmarks`
- Approval, rejection, revision, finalization, report review and outcome routes.

Planner-level actions include source preparation, task edits, evidence imports, recommendation generation, scenario creation/repair and draft preparation. Add frontend role tests that prove a Viewer cannot mutate, a Planner cannot validate or benchmark, and an Officer can complete the review flow.

## 5. AI assistance and automation status

The current AI layer is optional and advisory. OR-Tools remains the scheduling engine. The OpenAI Responses integration can create structured recommendation explanations, report-summary drafts and incident-field extractions. These calls are explicit user actions; the scheduler and background monitor never call the LLM automatically.

Set `OPENAI_API_KEY`, `OPENAI_MODEL`, `AI_DATA_POLICY=synthetic` for the seeded fixtures, and `AI_DAILY_CALL_LIMIT` in the backend secret manager. Use `AI_DATA_POLICY=authorized` only after the data owner approves sending imported evidence or free text to the provider. Local narrative extraction, ridge-regression evaluation and report-monitor automation work without an LLM key. Automation checks evidence, saves alerts and prepares idempotent MIS/PAM drafts for current approved recommendations; it does not approve, dispatch or submit reports upstream.

The production follow-up is to define which AI actions may run on a schedule, add provider monitoring and cost controls, and connect only authorized live source snapshots.

## 6. Realtime and source integration

The current prototype refreshes React Query data after actions and polls long-running jobs. It does not yet subscribe to Supabase Realtime and does not connect to live COA, ROAMS, TMS, SMMS, TDMS or BDMS systems.

For a production pilot:

- Define an authorized source contract for each upstream system.
- Add authenticated, retryable connector workers with source timestamps and freshness states.
- Use immutable source snapshots and optimistic concurrency checks for planning decisions.
- Add Supabase Realtime or server-sent events only for approved status updates; never bypass FastAPI authorization for planning mutations.
- Keep the OR-Tools result advisory until railway officers validate constraints and operational rules.

## 7. Production controls still required

- Enforce HTTPS origins, secure cookies/session settings and MFA assurance for operational accounts.
- Use a private PostgreSQL schema, backups, monitoring and a dedicated database role.
- Keep one API process per current deployment database until the solve queue is moved to a durable worker queue.
- Add retention and access rules for profile data, especially date of birth.
- Replace SQL-based first-user setup with a documented bootstrap procedure and a second-admin safeguard.
- Add automated browser coverage for each role and the complete invitation → approval → sign-in journey.
- Test deployment with real Supabase and SMTP credentials in a secret manager; never commit them.

## 8. Acceptance criteria

The next implementation is complete when:

- An invited or self-registered user can be reviewed and assigned access from the Admin page without SQL.
- The same account immediately receives the correct role-specific controls after a fresh sign-in.
- Viewer, Planner, Officer and Admin browser tests cover allowed and denied actions.
- Officer validation and benchmark actions are blocked at both the UI and API layers for lower roles.
- Audit history identifies who changed access and when.
- A documented source snapshot can be imported, planned with OR-Tools, validated by an Officer and exported without losing evidence references.
- Production secrets, live connectors and realtime behavior are explicitly configured or visibly reported as unavailable.
