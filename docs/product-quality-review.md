# RailBLOX product quality and COA workflow review

Review date: 14 September 2026. Scope: repository application, four existing roles, supplied public manual, local production build and isolated tests. This review does not assert access to the railway's current intranet deployment.

Implementation and verification continued on 15 September 2026.

Layout revision, 16 September 2026: restored the original RailBLOX logo to a full-width top masthead following user feedback. Block queue, Planner, Train movements and Operations use the top navigation; maintenance, evidence, reports and workspace tools use a separate supporting sidebar. Removed decorative navigation icons and the diagram's background grid, reduced rounded-card styling, and retained functional charts and status cues. Mobile supporting navigation remains keyboard accessible; both navigation surfaces preserve the selected network and query context.

## Reference and comparison

The supplied [CRIS CCMIS user manual](https://coamis.indianrail.gov.in/Contents/CCMIS_USERMANUAL.pdf) identifies itself as a beta manual with an April 2021 preface. It describes centralized COA MIS rather than a maintenance optimizer. Its workflows include current/archived charts, train enquiry, movement/source summaries, running hours, light-engine and interchange reports, caution/block/unusual registers, login summaries, TSR/data-logger reporting, station-pair enquiries, exports, password changes and support contacts. This is a reference baseline, not proof of the live product's 2026 feature set.

| Reference workflow | RailBLOX result after this change |
| --- | --- |
| Chart and train enquiry | New snapshot occupancy chart, date/time range, direction/category/search filters, station-pair enquiry, detail view, table and CSV. |
| Cautions and blocks | Searchable, section-filtered, date-scoped registers over saved evidence; CSV and browser printing. |
| Unusual reporting | Historical incident evidence can be inspected/exported; no official unusual-event register is claimed. |
| Profile and user access | Professional details, security, cumulative permissions and personal audit activity; four server-enforced roles. |
| Source, running and punctuality reports | Some evidence is already available in Operations/Insights. Actual passage, halt, speed, cancellation and source-completeness data remain missing. |
| Multi-division, telemetry and official returns | Requires authorized interfaces, tenancy design and owner acceptance; not implemented. |

## What made the existing interface feel unfinished

1. **Competing navigation layers.** Removed the duplicate account strip and second top menu. The revised masthead restores the preferred brand placement, with four operational tabs and a 218 px supporting sidebar. Mobile navigation exposes the same workflows with keyboard focus and Escape handling.
2. **Weak visual hierarchy.** Repeated decorative icons and red actions competed with planning information. Shared navy/blue tokens, quieter metadata, restrained borders, consistent panel headings and a smaller footer now prioritize the task. Existing diagrams and critical workflows are preserved.
3. **Basic profile presentation.** Identity and security shared two loosely organized cards, while role descriptions concealed the full inherited access. Replaced with an identity summary and Details, Security, Access permissions and Activity sections. Designation, department and office are editable descriptive metadata, never authorization inputs.
4. **Direct navigation failure.** Availability dereferenced an unloaded snapshot. It now uses the same loading/error boundary as the other operational routes and has an explicit retry path for availability-service failures.
5. **Hard-to-inspect operational data.** Train rows existed only as flat source inputs. The new enquiry screen provides a time/station picture, filters, provenance, a details drawer and a matching export. Caution/block information is now searchable through dedicated registers.
6. **Insufficient account guidance.** Added a workflow guide, a four-role matrix, recovery guidance and a path from profile to user administration. Technical connector configuration stays out of ordinary operational actions.
7. **Fragile application failure state.** Added a root error boundary that offers a reload instead of a blank screen. Saved records remain server-side.

## Access implementation

| Role | Responsibilities |
| --- | --- |
| Viewer | Read records, inspect movement/evidence views, export data and see only their own account activity. |
| Planner | Viewer capabilities plus input editing/imports, mappings, proposal generation, scenario repair, analysis and draft preparation. |
| Officer | Planner capabilities plus formal validation, benchmarks, approval/rejection, commitment revision, cycle finalization and actual outcomes. |
| Administrator | Officer capabilities plus reviewed user grants/revocation, invitations, automation and division audit access. |

The server policy is explicit for each write route and rejects unclassified non-admin writes. A UI-disabled button is not the security boundary. Supabase administrator-controlled metadata supplies role/division; self-edited professional fields cannot grant access. Existing MFA, pending-account handling, stale access-change checks, self-demotion protection and audit recording remain in force. Production enforces an authenticator for operational roles. The permissions matrix is sourced from the backend catalogue.

`GET /api/auth/activity` selects the current actor and division in SQL before applying its 20-event limit. It returns action, record reference and timestamp only, not other users' events or raw audit payloads.

## Data semantics and limits

The movement chart shows immutable section-occupancy estimates, with uniformly spaced stations. It does not infer train speed, station dwell, confirmed passage or punctuality. Section minutes sum only the overlap with the enquiry interval. Station-pair filtering requires an ordered, connected route; it does not match an unordered pair of station names. CSV includes snapshot identity, timestamps and the estimate basis and neutralizes spreadsheet formula prefixes.

The selected plan version provides the maintenance overlay; version/date controls preserve historical inspection. This is not a live or archival feed from COA. A time interval ending does not establish that a real restriction was cancelled or a block handed back. Incident evidence uses recorded historical narratives, not manufactured operational incidents. Unknown fields remain unknown.

## Remaining work before a real pilot

- Agree source contracts and authorized access for COA/RTIS/REMLOT/data loggers, ROAMS and departmental feeds. Define completeness, freshness, source identifiers, cancellation/closure semantics and outage handling.
- If multiple divisions must share a service, design database-level tenant isolation and cross-division grants. The current deployment deliberately serves one division per database.
- Validate a real production image behind HTTPS with Supabase and PostgreSQL. Test real invitations, confirmation, MFA, password recovery, role removal, SMTP delivery and restored backups. Mocked provider tests cannot prove these integrations.
- Have an operational owner accept the modeled constraints and the meaning of approvals and actual outcomes. RailBLOX does not dispatch trains or authorize work.
- Configure monitoring, incident contacts, retention, session lifetime, secret rotation and an administrator recovery process.

The earlier generated `output/pdf/RailBLOX_User_Manual.pdf` is not regenerated here and may describe the previous interface. Use the in-app guide and this review for the changed workflows.

## Verification performed

- Backend: full suite **63 passed**. After correcting DOWN-direction station traversal, the focused access/enquiry/preflight suite was rerun: **6 passed**. It covers both travel directions, disconnected legs, interval clipping, CSV formula protection, per-user activity isolation, the four-role policy and configuration redaction.
- Browser: full suite **27 passed**. Tests cover sign-in/out, MFA, requested versus assigned access, role changes, profile persistence, invitations and audit feedback, planning/repair/approval/exports, direct Availability loading and retry, first-plan empty state, train enquiry and operational registers. After the final DOWN-direction correction, all **7 focused screen tests passed**, including DVR-to-ARV enquiry and the reversed station sequence in train details.
- Screenshots and layout assertions: 1440, 1024 and 390 px, plus the existing 200% zoom and keyboard checks. Profile Details, Security, Access permissions and Activity are checked. Scrollable tables retain accessible labels without widening the page.
- Production build: TypeScript and Vite passed. The main JavaScript chunk is approximately **447 kB** before gzip; secondary pages load on demand. No chunk-size warning remains. The API defaults to `/service` in production instead of a visitor's localhost, and network requests have a 30-second timeout.
- Provider identity/email responses are mocked in automated browser and access tests. Live Supabase, SMTP, HTTPS ingress, PostgreSQL backup/restore and official railway interfaces are not verified by these results.

No changes were deployed to railway systems, and no real invitations or account changes were sent. The existing generated PDF was preserved. Source changes are available in the working tree for review.
