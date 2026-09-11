# Architecture and model assumptions

RaILBLOX is a local advisory prototype. All station names, topology, rules and task durations are synthetic. No live railway connection, official certification, accident probability, rupee saving or field-work authorization is claimed.

## Data and operations

- React/TypeScript/Vite, React Router and TanStack Query provide six connected routes. URL parameters carry corridor, selected plan, horizon, date and filters. Authoritative data stays in SQLAlchemy persistence.
- FastAPI exposes the API at `/docs` and `/openapi.json`. `domain.py` validates inputs. `frontend/src/types.ts` maintains the interface contract exercised by backend and browser tests.
- `adapters.py` parses bounded UTF-8 CSV/JSON. `canonicalization.py` converts explicit chainage units and timezone-aware dates. Raw preview rows survive commit. Stable `(source, source_record_id)` identities make imports idempotent.
- `footprints.py` filters directed sections, canonical asset identity, isolation groups and access types. Traffic protection and electrical access are independent requirements.
- `solver.py` builds optional CP-SAT work intervals, package intervals and resource cumulative constraints. `validator.py` independently checks serialized assignments against source data.
- `candidates.py` evaluates bounded singles, pairs and triples with local counterfactual solves. Existing assignments are fixed while evaluating a bundle; resources and margin are reported even for zero additional closure.
- `repair.py` creates a separate input snapshot. Freight delay shifts every subsequent occupancy by the entered amount. It does not model train queue interactions or report train delay savings.
- One bounded worker thread runs a single job at a time outside the API event loop. Job states persist. Startup marks abandoned jobs failed with a retry instruction. CP-SAT owns the optimization computation. The prototype is intended to run as one application process (`uvicorn` without multiple workers).

## Persistence

Alembic revision `0001` creates snapshots, per-snapshot entity rows, workspace heads, immutable plan/result documents and append-only audit events. Entity identity is normalized by `(snapshot_id, kind, id)`; typed entity payloads and immutable output schedules use JSON. Cross-entity validation is performed by the domain layer. This is a pragmatic prototype schema rather than separate relational columns/tables for every nested domain field.

Snapshots are immutable, and the corridor head advances with an expected-version comparison. Plans reference their exact source snapshot. Approval is derived from audit events, so it does not rewrite plan output. A validated explicit revision releases eligible unstarted approvals; failed revisions leave approvals in place. Started task assignments remain fixed.

SQLite is the native default because Docker/PostgreSQL is unavailable in the development environment. Docker Compose configures PostgreSQL through the same repository layer and migrations. SQLite serializes local writes; PostgreSQL is the intended next step for concurrent use. Authentication and multi-process job coordination are outside this local prototype.

## Time and resource conventions

- Fixture anchor: **10 September 2026, 00:00 Asia/Kolkata**, stored as `2026-09-09T18:30:00+00:00`.
- Source/audit timestamps are timezone-aware ISO UTC values. Scheduling values use integer minutes relative to the explicit immutable snapshot anchor in both source payloads and solver output. They must always be interpreted together with that anchor; exported JSON contains it.
- Intervals are half-open `[start, end)`. Work ending exactly at another interval's start does not overlap.
- Resource requirements consume one unit of each listed resource for the full task duration plus the resource's configured setup/travel allowance. Capacity is checked over the complete plan. The default fixture uses conservative constant travel/setup allowances, not distance-derived routing.
- Preparation and restoration are package stages of ten minutes each. They require closure protection but no separately modeled crew. Testing is modeled as a task with a predecessor (C after A). Duration is never shortened to improve feasibility.
- Incompatible work classes cannot share one package, even if their task intervals could be serialized. Compatible tasks with independent resource capacity can run concurrently.
- Mandatory overdue work is retained for explicit infeasibility. Optional unverified or unready work remains visible and unassigned.
- Weekly refinement retains approved/started commitments within its actual horizon. Monthly solving considers actual source windows and tasks within 30 days, rather than multiplying a weekly result.

## Objective policy and status

1. Satisfy hard constraints, mandatory work, started work and approval locks.
2. Maximize the sum of configured eligible task service weights.
3. During repair, minimize changed existing assignments, then absolute start-time shift. New tasks are counted separately; dropped tasks count as changed without an invented start shift.
4. Minimize closed-section-minutes.
5. Break ties by task/package start sums with one worker and seed 42.

Each achieved objective is frozen before the next stage. The default total solve budget is ten seconds. If any stage returns only FEASIBLE, the planner stops and exposes FEASIBLE and that stage's bound. A budget exhausted before any solution yields UNKNOWN, never INFEASIBLE. Overall OPTIMAL requires every stage to prove its optimum. Stage results and bounds are included in JSON exports.

Closed-section-minutes is the union of closure intervals on each directed section. Several tasks in one package do not multiply its closure cost. No avoided-future-possession claim is made without an actual scheduled comparator.

## Fixtures and benchmark interpretation

`fixtures.py` is the generator of record; `python manage.py export-fixtures` writes its JSON and CSV artifacts. Small: ten tasks, three departments, six directed sections, four windows, explicit resources and two movements. Initial seed is a feasible mandatory-core plan, allowing judges to discover optional B and C. A normal Generate plan includes all feasible optional work. Full W1 is A+B+C (75 minutes, 15 margin); a 20-minute shortening retains A+B (60 minutes, 10 margin), with independent D unchanged. Impossible mandatory and unresolved mandatory cases are separate scenario actions.

Presentation: eight stations, fourteen directed sections, 100 tasks across all 30 days, 120 windows, 60 consistent freight movements, three departments, seed 42. Task durations and weights use the seeded RNG. Mandatory fixture tasks have verified locations; optional aliases include unresolved mappings. Night and weekend windows are represented by their real anchor-relative dates and times.

Benchmarks execute two greedy orderings, deterministic joint CP-SAT and adaptive repair. Greedy methods reserve accepted allocations and use the same feasibility model; this measures the ordering policy rather than an unrelated rule set. The three held-out shortening trials are 10, 20 and 30 minutes. Static invalid schedules count as failures. The table reports scenario passes, not a stochastic handback-success estimate. Runtime includes the method's measured execution, with no fabricated percentages. Unequal service coverage is flagged.

## Local limitations

- Illustrative source adapters import maintenance needs under TMS/SMMS/TDMS/COA/BDMS labels. They do not implement the production source interfaces. Movement and calendar disruptions operate on the canonical fixture data.
- The timeline starts with the fixture scale and expands within the selected day to include work, movement and planning-hold intervals. Source exports and the table retain full interval times. Horizontal chart overflow is confined to its labeled region. A table alternative and keyboard buttons expose package/task selection.
- The lock and audit workflow is a single-user demo, not secure authentication or a safety system.
- PostgreSQL/Docker startup requires verification on a machine with Docker installed. This environment verifies the SQLite path.
