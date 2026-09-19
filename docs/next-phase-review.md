# Next phase: account aliases and planning transparency

Reviewed 19 September 2026. This is a code-based assessment, not certification for railway operations. The existing logo, top operational navigation and supporting sidebar are retained.

## Account changes

- Signup and password recovery still require an email address. After email confirmation and division access approval, users choose an optional username under Profile > Details > Sign-in username.
- Usernames are unique within the deployment database, case-insensitive, and 3–32 ASCII characters. They start with a letter; remaining characters may be letters, digits, dots, underscores or hyphens. Reserved system names cannot be claimed. Names are stored lower-case, separate from editable identity-provider metadata.
- Migration `0002` adds a private registry with a unique username constraint and one alias per provider user ID. There is no password column. Concurrent claims are resolved by database constraints; changes check the previously displayed username. Changing an alias makes the old name available again. Deleted provider accounts do not automatically free their old aliases.
- Email login remains directly against Supabase. Username login uses `POST /api/auth/username-login` and needs the backend-only `SUPABASE_SERVICE_ROLE_KEY`: the server reads the current provider email by registered user ID, then verifies the password using Supabase's password grant and publishable key. Returned provider identity must match the alias owner. No public username-to-email resolution endpoint exists.
- Username requests are limited to 4 KB, 20 requests per minute per observed client address, and 8 per normalized username. Counters are bounded and process-local, matching the current single-API architecture. Add trusted edge rate limiting before a public rollout; a shared reverse-proxy address can make the IP limit shared across users. Provider limits also apply. Generic credential errors do not claim resistance to all timing-based enumeration. CAPTCHA integration is not included in this phase; if provider CAPTCHA is required, username login fails closed, not bypassed.
- Passwords, access tokens and refresh tokens are neither stored nor audited by RailBLOX. Only successful alias changes are audited, without the chosen alias or email in the event payload. Browser session persistence remains the existing Supabase client behavior.
- Aliases do not grant roles, bypass email verification, authorize a foreign division, or bypass enabled MFA. Existing role and provider-verification boundaries remain in force.

## Temporary MFA policy

`REQUIRE_MFA=false` now explicitly turns off RailBLOX's authenticator gate and operational-role AAL2 requirement, including in production mode. The testing template sets this value. Omitting the variable in production still defaults to true; invalid values fail startup. Existing enrolled factors are not deleted. Password verification, role checks and division scoping remain enabled. Profile > Security reports the testing policy.

For a deployed testing instance, set **the backend host's environment variable** to `REQUIRE_MFA=false` and deploy the updated backend. Editing an example file does not change Render's environment. Restore `true` before operational use. Preflight intentionally continues to report MFA-off as not production-ready.

No live Supabase settings, deployed environment, accounts or database were changed by local implementation. The previously reported exclusive-database-lock deployment issue is separate and remains unresolved by this phase.

## What the attached paper actually models

Morganti, Crainic, Frejinger and Ricciardi, *Block planning for intermodal rail: Methodology and case study*, Transportation Research Procedia 47 (2020), pp. 19–26, [DOI 10.1016/j.trpro.2020.03.068](https://doi.org/10.1016/j.trpro.2020.03.068). Reviewed the supplied PDF, including formulation pp. 23–24 and results pp. 25–26.

In that paper a **block is a group of freight wagons** moved together. It is not a protected maintenance closure. The formulation combines container-to-platform loading, block selection and freight flows across a three-layer train/block/container network with given train services. It minimizes operating/transport costs and penalties for lateness, demand splitting and unserved demand. Its experiments use a North American railroad case with 192 terminals, 519 trains, 5,264 demands and a seven-day cycle; it reports optimality gaps after 3 and 24 hours using CPLEX 12.7.0. Those experiments are not RailBLOX benchmarks.

| Aspect | Attached paper | RailBLOX evidence |
| --- | --- | --- |
| Planning object | Freight block and container demand | Maintenance task and possession work package: `domain.py`, `solver.py` |
| Algorithm | MILP, CPLEX | OR-Tools CP-SAT optional integer-minute intervals: `solver.py` |
| Decisions | Blocks, itineraries, container flows, loading platforms | Task selection, task start/end, window assignment, shared possession start/end |
| Capacity | Train/block length, 40/53-foot loading rules | Crew/equipment cumulative capacity; no-overlap protection by directed section |
| Time | Event-based cyclic train/block/container network | Integer-minute positions within a selected 7- or 30-day snapshot horizon |
| Objective | Freight costs and service penalties | Uptime proxy, service weights, repair stability, closed-section minutes, tie-break |
| Disruption handling | Alternative freight-service and demand variants | Shortened windows, freight occupancy delays, crew exceptions and urgent work |
| Common idea | Resource-constrained optimization and scenario comparison | Present, but with different variables and physical meaning |
| Paper-specific capabilities | Container/platform assignment, freight demand flow and train-length limits | Not implemented; not inputs in RailBLOX's model |

**Conclusion:** RailBLOX implements real optimization for maintenance possessions, but does not implement this paper's freight-block MILP. Replacing CP-SAT merely to use the name “MILP” would not add the paper's capabilities. Freight block formation would be a distinct product module requiring container demand, train capacities, loading rules and cost data; it is not silently added here.

## What existing maintenance planning genuinely does

Code reviewed: `backend/app/solver.py`, `footprints.py`, `protection.py`, `validator.py`, `candidates.py`, `repair.py`, `availability.py`, `intelligence.py`, `learning.py`.

The planner constructs optional task intervals inside shared possession windows, accounts for preparation/restoration time, imposes deadlines and predecessors, checks readiness and footprint compatibility, reserves crew/equipment calendars, and excludes fixed train/protection occupancy. Mandatory and started work, and retained commitments, cannot simply be dropped. A separate validator checks the returned schedule. Tests exercise conflicting trains, missing isolation, resource conflicts, altered durations, infeasible mandatory deadlines, opportunity bundles and preserved commitments during repair.

The staged objective freezes proven-optimal earlier values. A time-limited feasible stage stops the sequence and reports FEASIBLE, not global optimality. “OPTIMAL” means optimal for the encoded model, data, and policy—not optimal railway operations or certified safety.

## Predictive decision support: actual capabilities and gaps

| Component | Implemented method | Important limit |
| --- | --- | --- |
| Availability | Historical failures/exposure projected over horizon, capped probability proxy; repair time and fixed work-class benefit factors; scheduled downtime | Not a calibrated failure-probability model, degradation process, or remaining-useful-life forecast |
| Scheduling uptime coefficient | Additive task score from criticality, service impact, failure rate, repair hours and work-class reduction | Not direct optimization of displayed net availability; multiple tasks on the same asset can accumulate proxy benefit |
| Priority | Explicit weighted evidence policy | Score is not a learned safety probability |
| Duration estimate | Historical cohort or engineering fallback with sample-size/confidence labels | Limited samples and stale evidence constrain trust |
| Duration experiment | Ridge regression with chronological holdout; at least 30 outcomes, at least 20 training and 10 holdout records | Evaluation only; observed weather is not forecast weather; does not replace scheduler durations |
| Approval | Officer decision and audit history | Records a prototype decision, not official track-access authority |

The interface now groups Availability, Insights and Model & planning basis under **Predictive decision support**. Task preparation, opportunities and disruption repair stay under **Maintenance planning**. Context guidance identifies the role of each screen and links to the model explanation while retaining the selected corridor and query context.

## Network Rail strategy comparison

The supplied [Scribd document](https://www.scribd.com/document/529251952/NETWORK-RAIL-Asset-Management-Strategy) is the **February 2011** strategy, not a current 2026 standard. It describes balancing service outcomes, whole-life cost and risk rather than a drop-in MILP. The official [October 2014 strategy](https://www.networkrail.co.uk/wp-content/uploads/2019/03/Asset-Management-Strategy.pdf) is a separate historical companion, not the same edition.

RailBLOX already supports evidence provenance, work coordination, reviewed decisions and recorded outcomes. Missing strategic capabilities include lifecycle intervention costs, renewal-versus-maintenance options, budget constraints, deterioration models, asset-policy versioning and independently calibrated forecasts. These need verified data and owner-approved assumptions before meaningful optimization; no placeholder cost savings or compliance claims were added.

## Deployment and verification boundary

Deploy both backend and frontend from the same revision. Migration 0002 runs via existing Alembic startup under the single-process owner lock. Back up the deployment database first. Set `SUPABASE_SERVICE_ROLE_KEY` on the backend only for username support; email login remains available without it. Never use a `VITE_` prefix for this key.

Local tests use isolated SQLite databases and mocked Supabase responses. Live Supabase password/session behavior, PostgreSQL migration, hosted rate limits and the MFA-off setting must still be smoke-tested in the testing environment. No paper-specific freight model, new calibrated predictive model or live railway integration was introduced.

Verified locally on 19 September: **82 backend tests passed**, **36 browser tests passed**, and `npm run build` passed. Backend coverage includes the private alias migration, persistence, database uniqueness/lowercase constraints, current-email resolution, wrong-account rejection, generic credential failures, rate/body limits, MFA defaults/override, permission boundaries and existing solver/validator cases. Browser coverage includes email and username session flows, email-only registration UI, alias conflict feedback/persistence, recovery guidance, MFA-on and MFA-off paths, planning workflows, and responsive navigation. Desktop and mobile screenshots were reviewed. Two upstream test-framework deprecation warnings remain.
