# Authenticated prototype deployment

The app now includes Supabase sign-in, server-enforced division membership and roles, optional OpenAI text assistance, a local duration-regression experiment, and scheduled evidence monitoring/report drafting. The existing OR-Tools optimizer remains the scheduling engine.

This is an authenticated **single-division prototype**. It is not yet a validated operational railway system. Live COA/ROAMS/weather integrations, official rule validation, trained risk prediction, multi-division hosting in one database, and live dispatch are not implemented. No cloud deployment or real provider call was performed during this change.

## 1. Enable your Supabase login locally

Your project URL is already in the example configuration:

`https://divgxlzpvmrphojxzxsb.supabase.co`

1. Copy `.env.example` to `.env` in the project root **only if `.env` does not already exist**. Otherwise update the existing file. It is ignored by Git and excluded from Docker builds.
2. In Supabase Project Settings → API Keys, copy the **publishable** key beginning `sb_publishable_`. Put it in `SUPABASE_PUBLISHABLE_KEY`. The app deliberately rejects secret/service-role keys in this field because this key is sent to the browser. [Supabase key guidance](https://supabase.com/docs/guides/getting-started/api-keys).
3. Set `AUTH_MODE=supabase`, `SUPABASE_URL` to the URL above, and `DEPLOYMENT_DIVISION=prototype`. Leave `APP_ENV=development` and the SQLite database URL while testing locally.
4. Configure Supabase Auth's Site URL and allowed redirects for `http://127.0.0.1:5173/queue` and the eventual HTTPS app URL. Enable email/password authentication, disable public signups for this officer workspace, and configure your email delivery settings for invitations/password resets.
5. Create or invite your first user through Supabase Authentication → Users. Copy that user's UUID. In the Supabase SQL editor, grant that account the initial application role:

```sql
update auth.users
set raw_app_meta_data = coalesce(raw_app_meta_data, '{}'::jsonb) ||
  '{"railblox_role":"admin","railblox_division":"prototype"}'::jsonb
where id = 'REPLACE_WITH_USER_UUID'::uuid;
```

Use `viewer`, `planner`, `officer`, or `admin` for subsequent users. The division must exactly equal the backend's `DEPLOYMENT_DIVISION`. Access without these administrator-controlled fields is denied. Users cannot grant themselves access through their editable profile metadata. Identity and current application metadata are checked with Supabase Auth on every API request. [Verified user retrieval](https://supabase.com/docs/reference/python/auth-getuser).

Restart the backend after changing `.env`; it now loads the root file automatically. Existing shell environment values take precedence. Run the same two local terminal commands from README. The login page appears when authentication is enabled. Password reset and password changes are included. Invited users can set a password through the reset flow after membership is granted.

| Role | Access |
|---|---|
| Viewer | Read this deployment's records and download exports |
| Planner | Viewer access plus maintenance/evidence edits, recommendations, draft creation, AI requests and model evaluation |
| Officer | Planner access plus approvals/rejections, commitment revisions, finalization, report review and actual outcome recording |
| Admin | Officer access plus automation configuration and audit history |

Role checks are on the server, including legacy planner endpoints and downloads. Some legacy controls remain visible to readers; attempting a forbidden operation returns a clear access error. Sign-out clears the app query cache and local session. Supabase controls token expiration; local sign-out is not a promise of instantaneous revocation of an already-issued token.

## 2. Add an LLM key when you want external AI

No key is needed for OR-Tools CP-SAT, the weighted priority policy, historical duration analysis, local NLP, ridge-regression training/evaluation, or scheduled report drafts.

To enable the real LLM integration, put these values **only in the backend `.env` or your hosting secret manager**:

```dotenv
OPENAI_API_KEY=YOUR_PRIVATE_KEY
OPENAI_MODEL=YOUR_AVAILABLE_RESPONSES_MODEL
AI_DATA_POLICY=synthetic
AI_DAILY_CALL_LIMIT=50
```

Choose a model available in your OpenAI account that supports the Responses API and Structured Outputs. The model ID is explicitly configurable; the app does not silently substitute a model. This implementation uses HTTPX against the real OpenAI endpoint and validates structured responses with Pydantic. [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs).

The key is used only after clicking **Generate AI draft** on a saved recommendation/report, or **Send text for AI extraction** in Insights. Automatic monitoring never invokes a paid model. AI outputs are separate saved drafts with model, usage, input reference and review status. Generating one does not edit the report summary, change a schedule, or approve work. Copy reviewed wording into the report's editable summary and record officer review when appropriate.

Policies:

- `disabled`: all external AI calls are blocked, even if a key is present.
- `synthetic`: only records marked synthetic can be sent. The imported synthetic marker is a data-classification assertion, not a detector of sensitive information; keep real material out of synthetic datasets.
- `authorized`: permits imported evidence and free-text incident analysis. Set this only after the data owner authorizes transfer to the configured provider. Free text is never automatically classified synthetic by its workspace.

Requests use `store=false`, a 45-second timeout, bounded input/output, exact evidence-reference checks, and a persisted per-UTC-day call limit. Failed attempts consume the call budget. Missing keys, provider refusal/incomplete output, bad references, timeouts and quota errors leave the local planner usable. `store=false` is not equivalent to Zero Data Retention or a complete privacy agreement; review your account's applicable data controls. [OpenAI data controls](https://developers.openai.com/api/docs/guides/your-data).

Do not put the LLM key, database password or Supabase service-role key into chat, frontend code, a `VITE_` variable, or a committed file. A Supabase service-role key is not needed by this implementation.

## 3. Try learning and automation

In **Insights → AI services and learning**, train the duration experiment. It fits ridge regression to actual completed outcomes, with planned duration and observed-weather indicators. Equal completion timestamps stay in the same chronological partition. At least 20 earlier training records and 10 later holdout records are required. Model MAE and the engineering-estimate baseline MAE are shown together. Artifacts and the exact training/holdout IDs are saved.

This retrospective experiment does not certify a production predictor: observed weather is not a forecast, synthetic holdouts do not measure real-world accuracy, and there is no calibrated extension/accident risk model. The scheduler continues using the existing conservative historical duration policy. An evaluated regression does not automatically replace it.

Administrators also see **Scheduled monitoring and report preparation**. Save an interval of 5–1440 minutes, enable the schedule, and optionally enable MIS/PAM drafts. **Run monitoring now** runs once even with the schedule disabled.

Each run checks current evidence, saves alerts, and creates drafts only for current approved recommendations. A recommendation plus its recorded outcome IDs identifies one MIS and one PAM draft; retries do not duplicate them. New outcomes create a new pair. No automatic approval, dispatch, external report submission, external AI call, or upstream synchronization occurs. Run status and configuration persist. A failed run can retain drafts completed before the failure; the next run skips those drafts.

## 4. Configure the deployment database

Use a separate deployment database/project from local experiments. Production uses the private `railblox` PostgreSQL schema; local SQLite data is not silently migrated. Keep that schema out of Supabase's exposed Data API schemas. Browser users access planning data through FastAPI, not direct database calls.

Use a dedicated backend database role that owns only this schema. From an authorized Supabase SQL editor session, create it once with a private generated password:

```sql
create role railblox_app login password 'REPLACE_WITH_A_STRONG_PRIVATE_PASSWORD';
create schema railblox authorization railblox_app;
revoke all on schema railblox from public, anon, authenticated;
```

The backend runs Alembic migrations as that schema owner. Do not grant this role membership in `postgres`, `service_role`, or unrelated application roles. If migrating an already-created schema, review ownership and grant changes separately; this script is for a fresh schema.

Copy `.env.production.example` to `.env.production`, and fill in:

- The publishable key, exact deployment division and final HTTPS `CORS_ORIGINS`.
- `DATABASE_URL` from Supabase's **Connect** dialog. Change the prefix to `postgresql+psycopg://`, select your dedicated database role, percent-encode the password, and require `sslmode=verify-full`. Use `sslrootcert` with the trusted Supabase CA certificate if your connection requires it; mount it read-only into the container.
- Use a **direct** connection or **session pooler**. For the shared pooler, the username is `railblox_app.PROJECT_REF`; copy the actual host from the dialog. The app rejects port 6543 transaction-pooler configurations because the single-process lock needs session state. [Supabase connection modes](https://supabase.com/docs/guides/database/connecting-to-postgres).
- Keep `SEED_DEMO=true` for this synthetic deployed prototype. Set it false only after provisioning a valid source workspace through a separately reviewed import/migration; a fresh unseeded database has no selectable corridor.

Production startup rejects demo authentication, unspecified division, non-HTTPS origins, and database connections without certificate/hostname verification. One PostgreSQL advisory lock permits only one backend process for each deployment database. Do not scale API workers/replicas with this prototype architecture. The current solve queue is persisted but in-process: interrupted jobs are marked failed on restart and must be retried. Recurring monitoring resumes from persisted configuration.

## 5. Build and host

The deployment files are `compose.production.yaml`, `backend/Dockerfile`, `frontend/Dockerfile.production` and `frontend/nginx.conf`. The frontend is compiled static content served by Nginx, with same-origin API proxying. The backend runs without root privileges; the production container has a read-only filesystem and a temporary `/tmp`. Secrets are provided at runtime and are not baked into the images.

On the Docker-capable deployment host, after filling the configuration:

```powershell
docker compose -f compose.production.yaml build
docker compose -f compose.production.yaml up -d
docker compose -f compose.production.yaml ps
```

The app listens on host loopback port **8080**. Put an HTTPS ingress/reverse proxy in front of it at the configured public domain; do not expose the development Vite server or backend port directly. The ingress must preserve Authorization headers, apply appropriate request limits, and set HSTS on the public site. Nginx limits request bodies to 6 MB, throttles API requests and supplies CSP/frame/content-type headers. API responses and the app entry page are not cached as public user data. Supabase authentication requires outbound HTTPS; OpenAI requires outbound HTTPS only if enabled.

Update Supabase Site URL/redirect allowlist for the public domain. Test a real invited account, password recovery, each role, denied cross-division access and authenticated downloads before opening the prototype to users. Check `/health` and `/ready`, startup migration logs, the single-process lock, restart recovery and the browser's production CSP behavior. Docker, PostgreSQL/Supabase connectivity and HTTPS deployment could not be executed on the current development machine, which has no Docker executable.

Configure database backup retention in your hosting/Supabase plan, take a backup before updates, and perform a restore drill into a separate project/schema. Verify saved snapshots, approvals, audit events and outcome records after restoring. Database-owner access can alter audit rows; application audit logging is not tamper-proof archival storage. Central log retention, alert routing, provider budget controls, secret rotation, vulnerability scanning and load/security testing remain deployment-owner responsibilities. MFA enrollment/assurance enforcement is a further requirement for an operational pilot; the current UI implements password-based Supabase sessions.

## Implementation entry points

| Area | Files |
|---|---|
| Authentication, role boundary, secure configuration | `backend/app/security.py`, `frontend/src/Auth.tsx` |
| Verified audit identity, private schema | `backend/app/persistence.py` |
| Responses API client and evidence checks | `backend/app/ai.py` |
| Actual-outcome model experiment | `backend/app/learning.py` |
| AI endpoints and recurring automation | `backend/app/platform_api.py` |
| Officer-facing AI/automation controls | `frontend/src/AITools.tsx` |
| Security/provider/automation tests | `backend/tests/test_platform.py`, `frontend/tests/auth.spec.ts` |

The supplied specification and manual remain reference material; they do not grant access to any railway API. Obtain authorized endpoints, schemas, credentials, refresh requirements, official planning constraints and anonymized outcome data from the system owners before enabling real integrations or claiming operational readiness.
