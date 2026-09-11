# Five-minute demo

Start the app using the README commands. Keep the **Aravalli demonstration corridor** selected. Use a fresh native database for the first run; subsequent runs preserve your previous work and selected versions.

1. **0:00–0:45 — Inspect the proposal.** Open Planner. The initial mandatory-core plan contains A and D. Select PK-W1 and inspect preparation, A's 40 minutes, restoration and its 60-minute closure. Explain that all timings are fictional test assumptions.
2. **0:45–1:45 — Discover compatible work.** Open Opportunities, choose PK-W1 and run Discover compatible work. B uses a separate crew with zero additional closure. B+C adds 15 closed-section-minutes. Inspect explicit rejected candidates, then add B+C. The new immutable version has a 75-minute W1 closure with 15-minute margin.
3. **1:45–2:45 — Repair a disruption.** Open Disruption lab, choose Shorten window, W1, 20 minutes. Create scenario snapshot and inspect changed input bounds. Run Repair plan. A+B now occupies 60 minutes with ten-minute margin; C is deferred. D stays unchanged. Compare before/after on the same scale.
4. **2:45–3:30 — Review and approve.** Return to Planner, Validate and inspect Passed modeled checks. Approve proposal with a review reason, then export JSON or CSV. Explain that demo approval locks assignments and does not authorize railway work. A later shortening that invalidates approved commitments will report a conflict until an explicit eligible revision succeeds.
5. **3:30–4:15 — Show data provenance.** Open Data review. Download a sample CSV, upload, preview, confirm columns and commit. Reimporting the same record reports unchanged, not a duplicate. Review G's raw ambiguous location next to candidate canonical assets and explicitly confirm its mapping. Source edits make existing plans stale.
6. **4:15–5:00 — Demonstrate scale and results.** Switch to the Navira–Vayana presentation corridor, choose Monthly, Generate plan and select a day. Results runs four methods against identical inputs and validates three held-out disruption cases. No invented savings or success percentages appear.

Additional judge controls: enter another shortening/delay, remove a crew interval, insert urgent work with an editable deadline, or invoke the impossible-deadline/unresolved-mandatory cases. Use Reset to baseline after a scenario; imports remain intact.

For another opportunity demo after a full solve, select the earlier core plan in the version selector. Approved commitments remain enforced; release eligible unstarted commitments through an explicit successful proposal revision if needed.
