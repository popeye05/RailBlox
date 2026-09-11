# SPEC 3 implementation and deployment handoff

This delivery continues the existing React, FastAPI, Supabase Auth and OR-Tools application. The original SPEC 3 remains the requirements document. LLM keys are optional; local scheduling, statistics, NLP and monitoring remain available without them.

## Delivered behavior

| Requirement | Implementation |
| --- | --- |
| Account control | Named account button, initials, active route state, keyboard focus and mobile layout; profile navigation uses React Router. |
| Profile | Email, name, role, division, account ID, session assurance, name editing, password actions, sign-out and removal of a previously stored birth date. Demo actions are clearly disabled. |
| Signup / pending access | Configurable signup and DOB fields. Requested role remains user metadata only. Confirmed sessions awaiting assignment show an approval screen and can set a password without reading planning data. |
| Admin | Paginated, division-filtered user listing; email confirmation state; reviewed assignment/removal with a reason; invitations and latest audit events. Other divisions cannot be reassigned through this deployment. |
| Revocation | Explicit null role/division values account for Supabase metadata merge semantics. Current server metadata is checked on every API call. |
| Concurrency / admin safeguard | Expected role and division reject stale edits. Access changes serialize within the single API process and recheck the acting admin under the lock; self-demotion is forbidden. A second administrator should be configured for recovery. |
| Audit | Requested, confirmed and unconfirmed access changes are separate append-only events with actor, target, request ID and reason. Profile metadata/DOB and provider secrets are excluded. |
| MFA | TOTP enrollment/challenge UI and backend AAL2 gate. Production requires MFA for Planner, Officer and Admin; Viewer remains read-only. A verified low-assurance session may access its own account status to enroll, but cannot read operational records. |
| RBAC | Viewer read/export; Planner prepares inputs and proposals; Officer inherits preparation permissions and adds formal validation, benchmarking and review; Admin adds administration. Both API and UI enforce this cumulative hierarchy. Commitment revision remains Officer-only. |
| Refresh | Authenticated status polling every 30 seconds invalidates active planning queries when the source/audit revision changes. Identity rechecks on tab focus and every 30 seconds. No polling change approves or executes work. |
| Deployment status | Admin shows database, MFA, signup, LLM state and missing live connectors/realtime subscriptions. Missing admin credentials produce an actionable configuration error. |
| Local intelligence | The brief labels local evidence analysis accurately and counts eligible history without future outcomes or duplicate IDs. It does not claim a live railway feed or calibrated confidence score. |

Profile and Admin routes do not depend on having a loaded plan. Technical setup details live in this handoff and the Admin status panel; normal work screens retain role guidance and evidence inspection.

## First administrator without SQL

This operator procedure is only for a deployment with **no existing division administrator**. Existing administrators should use the Admin page. The command never sends an email.

1. Configure Supabase URL, publishable key, backend-only service-role/secret key, division and database environment on the backend host. `.env.production` must be supplied by the host/container; the local CLI loads `.env` by default, so do not accidentally bootstrap against the local configuration.
2. Create/invite the first account through the Supabase dashboard; have the owner confirm the email. Copy its UUID.
3. Stop the backend. In production the bootstrap takes the same PostgreSQL lease as the API before changing data.
4. From `D:\RAILBLOX\backend`, review the target:

```powershell
..\.venv\Scripts\python.exe -m app.bootstrap_admin --user-id USER_UUID --email admin@example.com
```

5. Apply the reviewed grant:

```powershell
..\.venv\Scripts\python.exe -m app.bootstrap_admin --user-id USER_UUID --email admin@example.com --apply
```

6. Restart the backend, sign in, enroll MFA if required, and assign a second administrator through **Admin → User access**. The CLI scans all account pages, checks email/UUID/confirmation and refuses to replace an existing administrator.

Do not use this as a recovery bypass. Lost-account/MFA recovery requires the deployment owner's Supabase administration process. Do not manually demote administrators while app access changes are in flight. Supabase and the application database cannot share one transaction: an interrupted provider request may have applied remotely. Reconcile `user-access-unconfirmed` or an incomplete requested event against the current provider account before retrying.

## Configuration

Development preserves existing signup behavior. Production uses these defaults:

```dotenv
APP_ENV=production
AUTH_MODE=supabase
SUPABASE_SERVICE_ROLE_KEY=SET_PRIVATELY_ON_BACKEND
PUBLIC_SIGNUP_ENABLED=false
COLLECT_DATE_OF_BIRTH=false
REQUIRE_MFA=true
AI_DATA_POLICY=disabled
```

- `APP_ENV=production` always enforces MFA for operational roles even if `REQUIRE_MFA=false` is accidentally supplied. Local MFA testing can use `REQUIRE_MFA=true` with development mode.
- Also disable public signup in Supabase Auth. The app toggle controls its registration UI; it cannot change the upstream provider policy.
- Enable TOTP in Supabase and configure email delivery plus exact Site URL/redirect allowlists. Invitations use the configured Supabase Site URL. Pending invite recipients can use **Set or change password** after confirming the link.
- Keep DOB off for production unless the data owner documents why it is needed and the retention period. The toggle stops collection/exposure, but does not erase old provider metadata. Users can remove their own DOB from Profile; the operator must define any bulk retention/deletion process separately. Account deletion and backups also follow the owner's retention policy.
- The SPA uses Supabase browser sessions and bearer authorization, not authentication cookies. CSP restricts scripts; API responses are no-store; sign-out clears query data and the local session. Configure provider token/session lifetimes and MFA recovery policy before inviting pilot users. Do not claim that client sign-out instantly revokes all issued bearer tokens.
- Keep one API process and one database per division. Use the existing private PostgreSQL schema, dedicated DB role, TLS certificate verification, HTTPS ingress, CSP and secret injection in `deployment.md`.

## Source and automation boundary

The existing import contract is documented in [SPEC 2 implementation](spec2-implementation.md). Download source/evidence examples, import reviewed immutable snapshots, generate an OR-Tools recommendation, have an Officer validate/review it, then export the saved evidence or report. Feed timestamps, immutable evidence IDs and optimistic concurrency remain enforced.

No upstream endpoints or credentials were supplied for COA, ROAMS, TMS, SMMS, TDMS, BDMS or weather. Their live workers are **not configured**. SSE and Supabase Realtime are also **not configured**; authenticated polling is the implemented refresh mechanism. These limitations are visible in Admin → Deployment services. Connector workers require actual authorized schemas, authentication, retry policy, quotas and freshness expectations from the system owners; illustrative contracts are not official interfaces.

LLM actions remain explicit and optional. Scheduled monitoring checks evidence and prepares idempotent drafts, with no automatic external model requests. The persisted daily call limit is an application quota, not a currency budget; provider spend controls are configured in the provider account if LLMs are later enabled.

## Verification and remaining deployment gates

Local tests exercise actual CP-SAT solving, independent validation, source import, evidence/version conflicts, outcomes, report exports, role authorization and audit persistence. Supabase and email endpoints in automated tests are mocked: passing those tests does not confirm real SMTP delivery, MFA enrollment, or cloud policy configuration.

Before deployment, validate the production image behind HTTPS with a dedicated Supabase/PostgreSQL environment; exercise real invitation → confirmation → reviewed grant → sign-in → MFA and password recovery; verify all four roles; perform a database backup/restore drill; set alert routing, retention and secret rotation; review official railway constraints with the operational owner. No deployment or real invitation/credential change is performed by this delivery.

Reference contracts: [Supabase MFA](https://supabase.com/docs/guides/auth/auth-mfa), [TOTP](https://supabase.com/docs/guides/auth/auth-mfa/totp), [Admin invitations](https://supabase.com/docs/reference/javascript/auth-admin-inviteuserbyemail), [Admin account updates](https://supabase.com/docs/reference/javascript/auth-admin-updateuserbyid).
