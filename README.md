# RaILBLOX — local development

Working React + FastAPI + OR-Tools planning prototype. The original implementation specification is preserved below.

Supabase login and roles, optional OpenAI assistance, duration-model evaluation, and scheduled monitoring/report drafting are now implemented. Start with [authentication, API keys and deployment setup](docs/deployment.md). Local demo mode needs no keys; the external integrations require your configuration. Production container and live Supabase/LLM verification are still pending.

The SPEC 2 advisory MVP adds **Block queue, Operations, Insights and Reporting**, with evidence-based recommendations, local officer review, recorded outcomes and MIS/PAM drafts. Start at `http://127.0.0.1:5173/queue`. See [SPEC 2 implementation and integration handoff](docs/spec2-implementation.md) for methods, source contracts and production gaps. No external API key is required.

## Run locally (Windows / PowerShell)

Prerequisites: Python 3.13 and Node 22. The native database uses SQLite and is created once at `backend/railblox.db`. No external AI key is needed.

From the project root, install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock
cd frontend
npm ci
```

Backend terminal, from the project root:

```powershell
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Frontend terminal, from the project root:

```powershell
cd frontend
npm run dev
```

Open **http://127.0.0.1:5173**. API documentation: **http://127.0.0.1:8000/docs**. Liveness/readiness: `/health`, `/ready`.

The first startup seeds two synthetic corridors and computes mandatory-core proposals. Use Opportunities to add optional work, or Generate plan to optimize all eligible work. Dates are anchored to 10 September 2026, 00:00 Asia/Kolkata. Browser refresh and backend restart preserve imports, mappings, scenarios, versions and approvals.

Configuration names are listed in `.env.example`. The backend loads the root `.env` automatically; shell variables take precedence. Put `VITE_API_URL` in `frontend/.env` when changing the frontend API address. The defaults work without configuration. Never put private API keys in frontend variables. On macOS/Linux use `.venv/bin/python` instead of the Windows executable paths.

## Verify

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest -q
cd ..\frontend
npm run build
npx playwright install chromium
npm run test:e2e
```

The browser suite starts isolated test services on ports 8001 and 5174, using a separate SQLite database. It does not mutate your native demo. Responsive screenshots are saved under `frontend/qa-screenshots/`.

Docker alternative: `docker compose up --build` from the root. It uses PostgreSQL 17, Alembic migrations, and the same frontend/backend ports. Docker was unavailable on the development machine; the native SQLite startup and tests are the verified path. Compose credentials are local demo defaults, not production secrets.

## Fixture management and project notes

Regenerate committed samples from `backend`: `..\.venv\Scripts\python.exe manage.py export-fixtures`.

Explicitly rebase the demo without deleting source/import history:

```powershell
cd backend
..\.venv\Scripts\python.exe manage.py rebase --corridor small --anchor 2026-10-01T00:00:00+05:30 --confirm
```

This creates a new snapshot with the same relative-minute inputs and preserved imported records. Existing plans remain historical; generate a new plan. It does not silently change fixture dates or delete a workspace.

- [Five-minute demo](docs/demo.md)
- [Architecture, objective policy, assumptions and limitations](docs/architecture.md)
- [Development handoff](docs/development.md)
- [Verification results](docs/verification.md)

The frontend uses the requested navy operational shell with an SVG corridor, timeline/table alternatives, Radix accessible dialogs, Lucide icons and Tailwind/CSS. All six routes use backend operations. No publication or live railway integration is configured.

---

# RaILBLOX — Codex implementation specification

Build the web application described below. This file is self-contained; no earlier conversation or PDF is required. Implement the required scope, run it, and verify the main flows. Do not stop after scaffolding or producing a plan.

## 1. Product and outcome

RaILBLOX is a railway maintenance planning prototype for an SIH hackathon. It combines Engineering, Traction Distribution, and Signal & Telecom tasks into coordinated maintenance access windows, called possessions or maintenance blocks.

The central workflow is: review imported maintenance needs → generate a constraint-checked plan → discover compatible extra work → inspect an executable work package → introduce a disruption → compare a repaired plan → approve the proposal within the demo.

The app must visibly demonstrate three core capabilities:

1. Discover additional maintenance that fits within the infrastructure footprint of an existing package and calculate its marginal closure cost.
2. Generate smaller fallback packages for shortened windows, preserving mandatory work and preparation/restoration stages.
3. Repair disrupted schedules while minimizing changes to existing assignments.

Build a working operational dashboard. Open directly on the planner with populated synthetic data and usable controls. All prominent actions must perform their described operation. Generate results from backend logic rather than hardcoded success states.

This is an advisory prototype. Display a persistent, restrained badge: **Synthetic data · Planning demo**. Demo approval records an application decision; it does not authorize railway work. Never claim a live CRIS connection, official certification, or guaranteed railway safety.

## 2. Working instructions

- Inspect the repository and applicable AGENTS.md instructions first. Preserve compatible existing code and dependencies; extend the existing app when present.
- For an empty repository, use the stack below. Select compatible stable versions at implementation time and commit lockfiles. Do not blindly rewrite an existing project's framework.
- Make ordinary implementation choices autonomously. Record assumptions in the README rather than blocking on minor questions.
- Work in vertical slices: seeded data → backend operation → connected interface → verification. Temporary mocks are permitted during development but cannot be the final planner.
- Complete all required capabilities before optional extensions. If an environment restriction prevents a capability, state exactly what is blocked and which flows are affected.
- Keep the deliverable local unless publication is separately requested. Do not attempt to log into or modify railway systems.

## 3. Stack and project organization

| Layer | Default choice |
| --- | --- |
| Frontend | React, TypeScript, Vite, React Router |
| UI | Tailwind CSS, accessible shadcn/ui primitives, Lucide icons |
| Server state | TanStack Query; use URL parameters for shareable filters |
| Backend | Python, FastAPI, Pydantic |
| Persistence | SQLAlchemy, Alembic, PostgreSQL |
| Scheduling | Google OR-Tools CP-SAT |
| Graph operations | Python adjacency structures or NetworkX |
| Visualizations | SVG for corridor/timelines; a chart library for benchmark plots if needed |
| Verification | Pytest for scheduling rules; Playwright for critical browser flows |
| Local environment | Docker Compose plus documented native startup commands |

Separate `frontend/`, `backend/`, `sample_data/`, and `docs/`. In the backend, separate adapters, canonicalization, footprint expansion, candidate generation, solver, independent validator, repair, metrics, and persistence. Keep solver code out of API handlers and React components.

Provide `.env.example` with no secrets. Default frontend port 5173, backend port 8000. Make the API URL configurable and restrict development CORS to configured frontend origins. Provide health/readiness endpoints.

If PostgreSQL cannot run in the development environment, support SQLite through the same repository layer for the local demo and document the difference. A deployed browser-only environment cannot host the Python solver by itself; configure an actual backend URL instead of silently replacing it with simulated responses.

No external AI key should be required to run the core app.

## 4. Visual direction

Design a precise railway control workspace with a navy navigation rail, cool white working canvas, crisp borders, and clear typography. Use the corridor diagram and synchronized timeline as the distinctive visual centerpiece.

Suggested tokens:

- Sidebar: `#0B1526`; canvas: `#F3F6FA`; surface: `#FFFFFF`.
- Main text: `#17253B`; muted text: `#52647B`; border: `#D5DFEB`.
- Primary action: `#2458D3`; Engineering: blue; Traction: teal; Signal & Telecom: violet.
- Severity uses separate semantic colors and text/icon labels. Department color never implies severity.

Use a readable sans-serif with system fallbacks and monospace for IDs, times and chainage. Main text around 16px; regular labels at least 14px; secondary metadata at least 12px. Use moderate spacing, compact technical tables, 8–12px radii, and subtle elevation for overlays. Avoid decorative stock photography, 3D trains, oversized marketing headings, gradients, glass effects and excessive animation.

Desktop layout: approximately 224px sidebar, compact top bar, flexible main workspace and a 380–440px details drawer when open. At narrow widths, collapse navigation and stack controls. Timeline overflow belongs inside its own labeled scroll region; the entire page must not overflow horizontally.

Every chart needs a legend, units, selectable records and a tabular alternative. Keyboard users must be able to select a task, inspect a package and trigger planning. Preserve visible focus, sufficient contrast, reduced-motion preferences and usability at 200% zoom.

## 5. Navigation and shared context

Provide these routes, with `/` redirecting to `/planner`:

| Route | Navigation label | Purpose |
| --- | --- | --- |
| `/planner` | Planner | Weekly/monthly schedule and corridor view |
| `/tasks` | Maintenance | Task register and engineering details |
| `/data` | Data review | Imports, provenance and ambiguous mappings |
| `/opportunities` | Opportunities | Compatible additions and rejected combinations |
| `/disruptions` | Disruption lab | Controlled scenario changes and repair comparison |
| `/benchmarks` | Results | Computed baseline comparisons |

Shared context includes corridor, planning date, horizon, scenario, input snapshot version and selected plan. Keep this consistent across routes and after refresh. Store authoritative plans and scenarios on the backend; do not use localStorage as the database.

Top bar: corridor selector, date/horizon control, synthetic-data badge, source snapshot timestamp and plan status. Show backend unavailability as a service error rather than as an empty dataset. Use a notification/toast for completed actions, with persistent details for errors requiring action.

## 6. Planner screen

The initial viewport must show useful plan content. Seed and compute an initial plan on first initialization, or show the seeded tasks and a clear Generate plan action while it is calculated.

Required elements:

- Metrics: tasks scheduled/eligible, mandatory deadlines met/required, closed-section-minutes, unresolved records, and changed assignments when viewing a repair. All use the selected snapshot and plan.
- Primary actions: Generate plan, Validate, Compare versions, Export and Approve proposal.
- A 2D corridor diagram showing station codes, directed lines, section IDs, selected task locations and toggled isolation overlays.
- A schedule timeline with section/package rows, a visible time axis, maintenance intervals, protected train occupancy, package stages and a now/simulation-time marker.
- Weekly overview with a selected-day detail view; monthly overview with aggregated package counts and a drill-down into a selected week/day.
- A separate unscheduled-work panel with reasons and deadline/deferral indicators.
- Filters for department, priority, section and status. A clear Reset filters action.

Selecting a task on the timeline must highlight its location and open a details drawer. Selecting a package shows preparation, concurrent work, dependencies, testing/restoration and handback. Show planned duration, available window and remaining margin.

Dragging a task, if implemented, creates a proposed edit validated by the backend before becoming an active plan. A form-based Move task action is sufficient for the required scope. Never permit a visual drag to silently bypass constraints.

Approval is disabled when no feasible validated plan exists, relevant required mappings are unresolved, input data changed, or a conflict invalidates the plan. Approving writes an immutable audit event and locks selected commitments in the demo. Show currentness and solver outcome separately from approval status.

Monthly planning must use tasks and windows within its actual 30-day horizon. Weekly refinement must preserve relevant locked commitments. Unscheduled work remains visible and only gains a deferral event when a planning cycle is explicitly finalized; rerunning a solve must not repeatedly increment deferral counts.

## 7. Maintenance and task details

Show a searchable, sortable table of tasks: ID, department, asset, section/line, work type, priority band, due date, mandatory flag, estimated work duration, required access type, assigned package and status.

Add/edit tasks through a validated form. Detail views include raw source remarks, source record ID, source timestamp, exact chainage, isolation groups, verification status, materials readiness, crew and machine requirements, predecessors, earliest start, due date, interruptibility and plan history.

Explain priority using explicit configured factors. Mandatory requirements and modeled protection rules cannot be relaxed using weight sliders. Keep opportunity value separate from urgency. Do not present a hand-authored risk score as an accident probability.

## 8. Data review and import

Provide downloadable sample CSVs and JSON representing the roles of TMS, SMMS, TDMS, COA and BDMS. Clearly label their schemas as illustrative. Do not claim they match production interfaces.

Import flow: choose source → upload → preview columns and validation errors → confirm mapping → commit valid records → show import summary and unresolved records. Reject unsupported content and oversized files with a clear error. Parse server-side with a bounded file size, default 5 MB. Treat uploaded text as data, never as executable code.

Use stable source-record IDs for idempotent import. Record inserts, updates and rejected rows. An unchanged reimport must not duplicate tasks. Preserve raw input alongside canonical values and mapping decisions. Validate dates, units, direction, positive durations and foreign keys. Never silently guess whether chainage is in meters or kilometers.

Match locations using verified asset ID, section, line and chainage. Alias matching can suggest candidates. Provide a side-by-side record review with candidate locations and explicit Confirm mapping action. Keep unresolved tasks out of automatic assignment. A mandatory unresolved task must prevent the app from claiming all mandatory work is covered.

Source tiles show last import, record count and connection state: Sample data or Imported file. Never label a CSV import as a live integration.

## 9. Opportunity discovery

For a selected proposed package, list eligible extra tasks and the result of adding each to that package while preserving its existing commitments. Include planned future tasks only if their earliest-start and maintenance eligibility allow bringing them forward.

An opportunity record must contain candidate task IDs, existing package ID, compatible footprints, required additional resources, added closed-section-minutes, change in handback margin, service benefit and the source snapshot used.

Show explicit rejected candidates with concrete reasons: resource conflict, incompatible work zones, missing traffic protection, incorrect isolation group, deadline violation, unverified asset or insufficient window. Check complete bundles, since pairwise compatibility does not establish group feasibility.

Add to proposed plan invokes the backend and creates a new validated plan version. Do not modify the old plan. A zero-extra-downtime opportunity can still consume resources or reduce margin; show both. Only claim an avoided future possession when the comparator actually scheduled it and the new version removes it.

Required implementation: footprint-filtered pairs/triples and local counterfactual solves. Keep candidate generation bounded for interactive operation. Explain computations using structured facts and templates; an LLM is optional.

## 10. Disruption lab

Provide a scenario form and four presets:

1. Shorten a selected window by an editable number of minutes.
2. Delay a selected freight movement, updating its subsequent section occupancies consistently.
3. Make a selected crew unavailable during a specified interval.
4. Insert an urgent task with editable duration and deadline.

Create a separate scenario snapshot. Show its changed inputs before running Repair plan. Keep the original baseline intact. The demo must accept judge-entered values; do not hardcode results for four preset buttons.

Show before/after timelines on the same scale, changed-task count, absolute start-time shift, deferred work, mandatory coverage, closure cost, validation status and measured runtime. Explain each changed assignment from actual inputs and decisions. Provide Reset scenario without deleting imported source data.

Maintain valid approval locks and started work. If an event makes a locked/started plan infeasible, display the operational conflict and require an explicit proposal revision for eligible unstarted commitments. Never shorten or discard an in-progress indivisible task to make a solution fit. The first prototype has no authority to implement field recovery procedures.

## 11. Domain model and time conventions

Use UUIDs or stable fixture IDs. Store timestamps as timezone-aware UTC values; display railway planning times in Asia/Kolkata with the timezone visible. Use integer minutes relative to each planning horizon for CP-SAT, with explicit conversion. Use half-open intervals `[start, end)` consistently.

| Entity | Required information |
| --- | --- |
| Corridor/section | Station endpoints, directed line, section ID, chainage range, topology relationships |
| Asset | Canonical/source IDs, section/line, chainage, isolation groups, verification and provenance |
| Task | Department, asset, mandatory flag, eligibility/deadline, duration, work class, resources, footprint requirements, predecessors, readiness and status |
| Resource | Type, capacity, availability intervals, location, configured travel/setup time |
| Movement | Direction, ordered section occupancy intervals, forecast timestamp, scenario |
| Window | Time bounds, covered sections, access types, isolation groups, candidate/proposed/approved state |
| Stage | Preparation/work/testing/restoration, duration, requirements and predecessors |
| Package | Tasks, stage schedule, footprint, window, mandatory core, optional variants |
| Plan | ID, parent version, scenario/input/rule versions, horizon, objective values, solver outcome, approval state, validity/currentness |
| Import/mapping | Source rows, checks, proposed/resolved values, confirmation history |
| Event/run | Scenario inputs, actor/reason, timestamp, background-run status and measured results |

Use a normalized schema and migrations. Store immutable plan outputs and audit events. Keep seeded synthetic rule IDs separate from real published railway standards. A dependency graph is an explicitly configured model, not a claim of causal learning.

## 12. Scheduling and validation contract

Use optional intervals, task assignment decisions, package activation and resource constraints. Required checks include:

- Mandatory tasks selected for the horizon meet their modeled deadlines; include mandatory overdue tasks for explicit infeasibility/escalation handling.
- Optional tasks are either assigned once or left unscheduled with a reason.
- Work occurs only within its eligibility interval and available possession window.
- No overlap with protected train occupancy on the affected directed sections, including configured margins.
- The package's traffic and electrical requirements are both satisfied. Electrical isolation alone never implies traffic protection.
- Crew/equipment calendars and capacities hold across the complete plan, including configured travel/setup.
- All predecessors, incompatible work classes, preparation and restoration stages are respected.
- Work duration is not reduced to improve fit; handback is before the window ends.
- Started work and valid approval locks remain fixed.

Distinguish stages sharing a possession from conflicting possession intervals: compatible tasks can run concurrently inside one package. The closure is occupied once by that package. Check internal work/resource compatibility separately.

Use a documented lexicographic policy: satisfy hard constraints; maximize weighted eligible maintenance service; during repair minimize changed assignments and then total start-time shift; minimize closed-section-minutes within the retained service/repair level. Include enough tie-breaking for repeatable fixtures. Do not minimize downtime by dropping mandatory or comparable useful work. Preserve stage-optimum guarantees honestly when a lexicographic solve hits its time limit.

Default solve time limit around 10 seconds, configurable. Record solver status (`OPTIMAL`, `FEASIBLE`, `INFEASIBLE`, `UNKNOWN`, `MODEL_INVALID`), objective values/bounds when available, runtime and instance size. Never report a timed-out unknown result as infeasible or as optimal. A previous candidate can be reused only if revalidated against current inputs.

Run an independent validator over output schedules using source data rather than solver booleans. Return structured violations with rule ID, involved records and intervals. Describe success as Passed modeled checks. Return concrete diagnostics for rejected assignments; do not claim globally minimal explanations without establishing minimality.

## 13. Required deterministic fixtures

Seed two datasets with documented generation rules and stable random seeds.

**Small acceptance fixture:** ten tasks, three departments, one short corridor, explicit resources and windows. Include the following package with deliberately compatible fictional tasks; these durations are software test assumptions, not engineering instructions.

| Stage/task | Minutes | Dependency |
| --- | ---: | --- |
| Preparation | 10 | Before work |
| Mandatory A | 40 | After preparation |
| Optional B | 25 | Parallel with A using a separate available crew |
| Optional C | 15 | After A |
| Restoration/handback | 10 | After all selected work |

All optional tasks have positive service value; full work fits a 90-minute window with duration 75 and margin 15. If the window is shortened to 70 minutes before work starts, A+B fits with duration 60 and margin 10; C cannot fit. Ensure no other constraints obscure this fixture's intended result.

Also include a same-location incompatible pair, a shared-resource capacity conflict, an ambiguous asset record, an impossible mandatory deadline and a valid independent package that should remain unchanged under a local disruption. Isolate impossible cases as separate scenarios so the initial demo can generate a valid plan.

**Presentation dataset:** a fictional corridor of about 8 stations/14 directed adjacent sections, roughly 100 tasks across 30 days, explicit isolation groups and a consistent passenger/freight occupancy dataset. Include weekend/night windows, overdue optional work, different resources, upcoming eligible work and deliberately messy source aliases. Label all places and topology as synthetic. Generate feasible baseline cases intentionally; place adversarial violations in selectable scenarios.

Store the fixture anchor date so saved plans remain reproducible. Display that demo date, and provide an explicit rebase/reset command rather than silently changing historical fixtures on every launch.

## 14. API and background operations

Publish typed request/response schemas through FastAPI OpenAPI. Generate frontend types or maintain one validated API contract. Use structured errors with code, message, details and request ID.

| Endpoint | Behavior |
| --- | --- |
| `GET /api/context` | Corridors, active demo date, snapshot and available plans |
| `GET/POST /api/tasks` and `PATCH /api/tasks/{id}` | Paginated retrieval and validated edits |
| `POST /api/imports/preview` | Parse file and return rows/mapping errors with preview ID |
| `POST /api/imports/{id}/commit` | Commit reviewed records idempotently |
| `GET /api/mappings` and `POST /api/mappings/{id}/resolve` | Retrieve and confirm asset mappings |
| `GET /api/corridors/{id}/topology` | Canonical topology, assets and isolation overlays |
| `GET /api/windows` and `GET /api/movements` | Horizon/scenario-filtered planning inputs |
| `POST /api/plans/generate` | Start a solve for an explicit input snapshot |
| `GET /api/runs/{id}` | Queued/running/succeeded/failed status and result ID |
| `GET /api/plans` and `GET /api/plans/{id}` | Plan history and complete selected output |
| `POST /api/plans/{id}/validate` | Independent validation |
| `POST /api/plans/{id}/opportunities` | Compute bounded compatible additions |
| `POST /api/plans/{id}/revise` | Add/move tasks or change eligible commitments in a child plan |
| `POST /api/plans/{id}/approve` | Check validity/currentness, record reason and expected version |
| `POST /api/scenarios` | Clone baseline snapshot and apply validated disruption |
| `POST /api/scenarios/{id}/repair` | Start repair against the referenced baseline plan |
| `POST /api/benchmarks` | Run specified methods on identical snapshots/seeds |
| `GET /api/benchmarks/{id}` | Progress and measured comparison results |
| `GET /api/plans/{id}/export?format=json\|csv` | Download data for the selected plan |

Names may be adapted to the existing app while preserving these contracts. Long operations should return `202` with a run ID and execute outside the request's event loop. A bounded worker/process executor is sufficient for the prototype; persist run status and mark interrupted jobs appropriately on restart. Poll with backoff and a clear error/retry path. Never show invented percentage progress.

Use input snapshot/version checks for approvals and revisions. Reject stale writes with a conflict response; surface a refresh/recompute action. Mutation endpoints need validation and immutable decision history. Do not expose a demo-actor selector as secure authentication. Real multiuser authentication is outside this local prototype unless already present in the repository.

## 15. Benchmark screen and metric definitions

Run four methods: sequential department-by-department greedy planning, combined deadline/priority greedy planning, joint deterministic CP-SAT, and the full adaptive planner. Baselines must use the same input data, resources, protection rules and independent validator. Sequential departmental planning reserves earlier allocations so it does not manufacture overlaps.

Display measured maintenance coverage, mandatory deadline coverage, closed-section-minutes, repair churn and runtime. Compare adaptive and static behavior on common held-out disruption scenarios. Static plans invalidated by a scenario count as failures, not successful low-runtime answers.

- Closed-section-minutes: sum over directed sections of the union of their closure interval lengths. Do not double-count tasks inside one closure.
- Work coverage: completed mandatory and optional task counts/weights, displayed separately.
- Churn: changed existing assignments and absolute start-time shift; newly introduced tasks shown separately.
- Simulated handback success: fraction of evaluated scenarios completing by their window end under documented duration/arrival assumptions. Show trial count and seed; omit the metric until actually simulated.
- Percentage reduction: `(baseline - new) / baseline * 100`; show N/A when the denominator is zero. Flag comparisons with unequal work coverage.

Provide a readable table and downloadable benchmark JSON/CSV. Do not invent rupee savings, accident reductions, predictive accuracy or performance percentages. Do not report train-delay minutes unless actual queue/occupancy propagation is implemented.

## 16. Error, empty and persistence behavior

Distinguish no tasks, no filter matches, no imported data, backend unavailable, invalid import, unknown solver outcome and infeasible plan. Every state needs an appropriate action, such as clear filters, retry, review record or inspect conflicts.

Disable duplicate actions while a job is active. Announce asynchronous completion accessibly. Preserve completed imports, mappings, scenarios and plan versions across refresh and backend restarts. Seed once by default. Reset only the selected synthetic demo workspace after an explicit confirmation; never delete user-imported records silently.

Export user-provided text safely for spreadsheets, including formula-leading values. Do not render inspector remarks as untrusted HTML. Keep secrets out of frontend bundles and logs. These are basic application requirements, not extra user-facing workflows.

## 17. Build sequence and definition of done

Implement in this order and continue through the required scope:

1. Scaffold/preserve the app, migrations, fixtures, shared types and polished navigation shell.
2. Build the real small-fixture solver, independent validator and connected planner timeline.
3. Add task editing, imports, mapping review and provenance.
4. Add footprint-based opportunity discovery and executable package inspection.
5. Add scenario creation, fallback selection, minimal-change repair and version comparison.
6. Complete weekly/monthly views, proposal approval, exports, persistence and benchmarks.
7. Verify browser flows, responsive states and clean startup; document actual results and limitations.

Required meaningful checks:

- The 90-minute fixture produces a 75-minute full package; the 70-minute variant produces the 60-minute A+B package.
- Incompatible work, shared-resource overflow, wrong footprint, train overlap and missing restoration are rejected by the independent validator.
- Mandatory infeasibility and unresolved mandatory locations are visible; no misleading all-clear state appears.
- A local disruption preserves the unaffected fixture package when service and hard constraints permit it.
- An invalidated approval cannot be reused; started indivisible work is not dropped.
- Repeat import does not duplicate records; confirmed mappings and plans survive restart.
- Monthly/weekly views use real horizon data and preserve relevant commitments.
- Solver timeout/status handling is truthful; metrics and exports correspond to the selected version.
- Browser flow: open seeded planner → inspect package → add an opportunity → inject disruption → repair → compare → validate → approve eligible proposal → export.
- Verify at approximately 1440px, 1024px and 390px widths, plus keyboard navigation and 200% zoom. Inspect screenshots for clipping, illegible chart labels and unintended overflow.

Deliver source, lockfiles, migrations, fixtures, `.env.example`, local startup instructions, a five-minute demo script, architecture notes and the tests needed for these checks. Run frontend typechecking/build and the relevant backend/browser tests. State checks actually run and any blocked checks. Do not claim completion while required buttons return placeholders.

## 18. Optional extensions — only after required scope works

- Decision-driven clarification: compare plans under alternative asset mappings and identify which unresolved fact changes a scheduling decision.
- Inspector-remark extraction with source spans and abstention, using an optional AI provider. Label a rule-based fallback accurately.
- Duration estimation from suitable historical records with held-out evaluation. Synthetic training demonstrates the pipeline only.

Do not add multi-agent auctions, causal failure forecasts, live government integration, train retimetabling, a 3D digital twin or a marketing landing page to the required build.

Start by inspecting the repository, choosing the smallest workable vertical slice, and implementing it. Continue until the required application and verification are complete.
