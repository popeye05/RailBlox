# Verification record

Development environment: Windows, Python 3.13.5, Node 22.17.0. Native SQLite repository and Alembic migration path.

Executed checks (updated for the authenticated prototype):

- Backend pytest: **42 tests passed**, including the original planner checks plus evidence validation, stale-feed rejection, duration uncertainty, NLP negation, weather/protection constraints, officer decisions, actual outcomes, report review, override horizons and prevention of generic approval bypasses.
- Frontend TypeScript and production Vite build: passed.
- Chromium Playwright: **11 tests passed**, including the original planner flow and the new assessment → recommendation → schedule/protection inspection → officer approval → outcome recording → draft review/export → narrative analysis flow. Saved records reopen after refresh.
- Layout tests passed at 1440, 1024 and 390 pixels for the planner, and 1440/390 pixels for the four decision-support routes, plus 200% document zoom checks. The page did not overflow horizontally. Timeline/table regions retain their own scrolling. All ten routes loaded.
- Screenshots from desktop and mobile were visually inspected: legible labels, contained diagram overflow, responsive navigation and stacked controls. Keyboard Tab focus and Escape-to-close were exercised; an automated test also verifies the table alternative.

Backend tests cover exact 75-minute/60-minute package durations and margins, independent D preservation, incompatible work, capacity overflow, asset footprint, train occupancy, restoration, duration tampering, electrical isolation, traffic protection, unresolved mandatory work, impossible deadlines, locks/started work, counterfactual pairs, actual monthly data, weekly locks, truthful UNKNOWN, freight propagation, union closure cost, idempotent import, mapping/plan/import persistence across restart, stale approvals, explicit revision and deferral events.

Additional backend checks cover unauthenticated access, every mutating route for readers, officer/admin boundaries, division membership, trusted audit actors across background jobs, production fail-closed configuration, structured AI evidence checks, persisted call quotas, idempotent report automation, chronological model evaluation and interrupted AI/monitor recovery. New browser tests cover the Supabase sign-in gate, session-bearing exports, sign-out/cache isolation, model training and persisted automation controls. Authentication and LLM provider responses are mocked in tests; no real login or paid model request was made. The final login changes were checked again with the two platform browser tests. The configured GitHub Actions workflow has not yet run on a remote repository.

Not verified here: live Supabase Auth/PostgreSQL, real OpenAI requests,  Docker/PostgreSQL startup (Docker executable unavailable), production hosting, screen-reader testing with a human operator, real railway rules/interfaces. Dependency warnings in the test run concern Starlette's future TestClient transport migration; all tests still pass.
