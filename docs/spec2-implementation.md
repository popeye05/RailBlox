# SPEC 2 implementation and integration handoff

Implemented locally on 11 September 2026. The original `SPEC 2.md` and supplied PDFs were not edited.

The authenticated prototype now adds Supabase roles, optional LLM assistance, local model evaluation and scheduled automation. See [deployment and credential setup](deployment.md) for these additions and the remaining validation steps.

## What to open

Start the backend and frontend using README.md, then open `http://127.0.0.1:5173/queue`.
The new Decision support navigation contains Block queue, Operations, Insights, and Reporting.
The existing Planner, Maintenance, Data review, Opportunities, Disruption lab, and Results remain available.
The supplied RailBLOX logos, Arial typography, and text navigation are retained.

## Scope and methods

This is an advisory prototype using explicitly synthetic fixtures or user-imported evidence. It is not a connection to COA, CCMIS, ROAMS, MIS/PAM, Network Rail, or a live weather service. Local analysis requires no external AI key. Optional LLM requests are disabled until server credentials and a data policy are configured; they run only through explicit AI actions.

| SPEC 2 capability | Implemented behavior | Limit |
| --- | --- | --- |
| COA-style operations | Source block reservations, caution orders, directed train occupancies and data freshness | Illustrative contract, not a production CRIS interface |
| ROAMS-style maintenance | CSV/JSON source option, downloadable examples, preview and existing validated commit workflow | Official schema and authorization required for a real connector |
| Priority selection | Seven supplied criteria, explicit weights, reasons and score interval for missing assessments | Rule-based policy, not a learned safety probability |
| Dependencies and conflicts | Predecessors, shared resources, incompatible classes, location, electrical access and movement conflicts | Same-section combination hints require a joint solve; hints are not approvals |
| Historical intelligence | Matched completed outcomes, extensions, average actual durations and source narratives | Seeded records are fabricated demonstration outcomes |
| Duration estimates | Actual/planned ratios matched by work class and department; section matching when enough records exist; empirical P20/P80 range and median | No calibrated confidence interval or validated operational ML model |
| Weather-aware planning | Explicit supplied weather hold intervals reach CP-SAT and the independent validator | No invented railway weather thresholds; a supplied hold is a demonstration policy input |
| Block recommendation | A saved derived snapshot combines priority, conservative duration allowance and unavailable intervals before solving | All existing hard constraints and commitment locks remain enforced |
| Explanation | Factor values, weight contributions, historical evidence IDs, limitations and candidate-window conflicts | Unknown criteria remain unknown |
| Officer workflow | Approve/reject with reason; request another window and rerun the model; append-only decisions | Verified Supabase identity and roles when enabled; explicit local demo identity otherwise |
| MIS/PAM drafts | Immutable populated draft, missing actuals, exceptions, editable reviewed summary, JSON export; scheduled drafting and optional separate LLM summary | Illustrative fields, no official submission |
| NLP | Local cause vocabulary, exact character spans, directed section matches, mentioned durations, basic negation and historical references | Severity and causality are not inferred; limited vocabulary requires review |
| Anomalies | Source freshness, recorded extensions, repeated incident mentions and actual duration above saved prediction | Explicit baseline thresholds, not learned accident or failure probabilities |
| Intelligence brief | Insights opens with a live local evidence brief: plain-language narrative, review signals and counts tied to the current snapshot | Deterministic advisory summary; no external LLM or safety authority is implied |

Actual execution observations are separately stored and tied to the approved recommendation. Engineering estimates, planning allowances, and actual durations remain separate fields. Feedback is eligible as history only after its completion time falls at or before the supplied evidence cutoff; outcomes from the future cannot leak into an earlier recommendation.

Priority weights are safety 25%, security 10%, operational impact 20%, criticality 15%, time sensitivity 15%, restrictions 10%, and combining 5%. These are disclosed prototype policy choices. The supplied workflow says **security of the defect**; its definition is unresolved, so seed assessments leave it blank. Missing factors contribute an explicit lower/upper score interval, not a secretly imputed value. Mandatory work is still a hard requirement.

Planning uses at least the engineering duration, with the empirical upper estimate as an additional allowance when available. Fewer than three matched outcomes produce no statistical range. Insufficient history remains visible. Predictions exceeding the supported task-duration limit are rejected for engineering review rather than silently shortened.

Historical evaluation uses a chronological 70/30 split and reports the number of actually evaluable held-out records, mean absolute error, and empirical interval coverage. Insights now also provides a saved ridge-regression experiment with holdout and baseline error. Synthetic evaluation is not evidence of performance on real railway data. A general knock-on train-delay simulator, seasonal causal model and production ML promotion pipeline are not implemented. Optional external LLM explanations do not change the scheduling model.

## Evidence workflow

1. In Operations, download the evidence JSON for the current source snapshot.
2. Review `snapshot_id`, `division`, `synthetic`, `as_of`, feed timestamps and source states.
3. Supply assessments, block reservations, cautions, weather periods and completed history using the displayed canonical section IDs. Preserve timezone offsets on timestamps.
4. Upload and explicitly validate/import the reviewed file. The server validates references, interval order, duplicate IDs, bounds and timezone-aware history. It creates a new immutable evidence ID.
5. Import ROAMS-style maintenance work through Data review using its CSV/JSON sample. A source change creates a new source snapshot; new task assessments start unassessed.
6. In Block queue, inspect the evidence and request a recommendation. Review the saved result before approving or rejecting it.

The `as_of` field is the explicit simulation clock for synthetic evidence. For imported non-synthetic data, feed freshness is also checked against the real server clock. Missing, unavailable, stale, or implausibly future-dated feeds block new recommendations and approvals. Updating evidence invalidates earlier recommendations for approval, while their recorded results remain inspectable.

An imported caution's speed is shown for officer review; it is not automatically converted into running-time changes without validated route/runtime rules. Set `work_prohibited` only for a supplied planning prohibition. Weather `planning_hold` and existing non-cancelled/non-completed block reservations create protected intervals. Overlapping fixed restrictions are merged for the solver, and each original restriction is independently checked by the validator.

Previously approved or started commitments are not silently resized to fit a new statistical allowance. If they conflict with a recommendation, the proposal can be infeasible. Resolve that explicitly through the existing revision workflow and recompute; do not delete the database to bypass commitments.

## API and persistence

Interactive contracts: `http://127.0.0.1:8000/docs`, under Decision support.

- `GET /api/intelligence/workspace?snapshot_id=...`
- `GET /api/intelligence/evidence/{snapshot_id}/sample`
- `POST /api/intelligence/evidence` with `{expected_evidence, evidence}`
- `POST /api/intelligence/recommend` with source snapshot, evidence ID, day and horizon; optional task/window/reason for a modification
- `GET /api/intelligence/recommendations/{id}`
- `POST /api/intelligence/recommendations/{id}/decision`
- `POST /api/intelligence/recommendations/{id}/outcomes`
- `POST /api/intelligence/nlp/{snapshot_id}`
- `GET/POST /api/intelligence/reports`
- `POST /api/intelligence/reports/{id}/review`
- `GET /api/intelligence/reports/{id}/export`

Recommendations use the existing bounded single-worker job queue and `/api/runs/{id}` polling. Evidence, recommendations, outcomes and report documents use the existing SQLAlchemy document store. Protected intervals are persisted in snapshot metadata; old snapshots load with an empty restriction list, so existing databases require no destructive reset. Decisions and report reviews use append-only audit events. The generic Planner approval endpoint cannot bypass evidence review for an intelligence-derived plan.

The workspace response also includes an intelligence brief built from the current feeds, priority assessments, duration history and alerts. It requires no API key and is the primary AI-like experience for the prototype; optional external LLM actions remain separate and explicitly triggered.

## Reference interpretation

- **CCMIS_USERMANUAL.pdf**, supplied by the user, preface dated April 2021: inspected the source-system architecture, report context and B1 block report (PDF page 44); C1 cautions (page 36) and U1 unusual incidents (page 50) distinguish those input roles. The document describes an intranet application and user screens, not a publicly usable integration API. Its historical division count was not adopted as a current deployment fact.
- **Workflow.pdf**, supplied by the user, page 1: inspected the handwritten TMS/SMMS/TDMS to BDMS to COA priority/approval flow and all seven printed criteria. These are requirements context, not instructions to access the systems.
- [Network Rail Operational Rules](https://www.networkrail.co.uk/industry-and-commercial/information-for-operators/operational-rules/), accessed 11 September 2026: engineering access windows and timetable planning are distinct inputs. This informed the separation of window protection from train occupancy. No UK rule was copied as an Indian Railway operating constraint.
- [Network Rail Possession Optimisation](https://safety.networkrail.co.uk/safety/industry-groups/wales-and-western-possession-optimisation/), accessed 11 September 2026: PodFlo and Railworks illustrate coordination, reviewable records and pre-filled end-of-shift reporting. Those workflow concepts informed the outcome capture and draft review screens; their software and forms were not replicated.
- [Network Rail weather response](https://www.networkrail.co.uk/our-work/looking-after-the-railway/responding-to-weather-impacts-on-the-railway/), accessed 11 September 2026: weather information is a planning input. The implementation accepts explicit forecast records and holds, without claiming Network Rail's forecasting capability.

## What the user needs to supply next

- An authorized/anonymized sample of maintenance requests, actual block outcomes, incident text and the fields required in MIS/PAM returns.
- The operational meaning and assessment scale for each priority criterion, particularly security of the defect.
- Reviewed weather restrictions, engineering duration policies, train-running margins and other railway rules.
- Official COA/ROAMS schemas, documented interfaces, read-only credentials, access permission and refresh requirements if live integration is intended. Do not place secrets in the frontend or commit them to the repository.

Before a shared operational pilot: configure and independently test the supplied authentication, secret management, HTTPS ingress, managed database/backups, audit access and monitoring; verify PostgreSQL and real source interfaces; add MFA assurance enforcement; validate models and constraints with authorized reviewers. Local browser/provider-mock tests do not establish these deployment properties. See [deployment and key setup](deployment.md).
