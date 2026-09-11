# SPEC.md — AI-Enabled COA Integration & Intelligent Block Planning

## 1. Overview

This project does **not replace COA, CCMIS, ROAMS, or other existing CRIS systems**.

The proposed solution is an **AI-powered intelligence and automation layer** that integrates relevant existing systems and makes **railway block planning smarter, faster and less dependent on manual analysis**.

The central idea is:

`Existing Railway Systems + Unified Data + AI Intelligence + Officer Approval = Smart Block Planning`

The AI acts as a **decision-support system**. Final operational and safety-critical decisions remain with authorized railway officials.

---

## 2. Existing System Context

### COA / CCMIS

The existing CCMIS system already centralizes COA data and provides real-time/backdated charts, dashboards and reports. It covers train movement, caution orders, blocks and unusual incidents. fileciteturn1file0L21-L25

The existing system already supports block reporting, including active/completed blocks and filtering by board, station, block section, direction and block type. fileciteturn1file0L443-L494

Therefore, our solution should **not recreate basic reporting or charting functionality**.

### ROAMS

ROAMS is an existing railway maintenance-related system. The project proposes connecting relevant maintenance/work information with COA so that maintenance requirements can directly contribute to intelligent block planning.

Exact APIs, schemas and integration permissions must be confirmed with the relevant CRIS/system owners.

### Other CRIS Systems

Relevant systems may provide additional authorized data, such as:

- RTIS — real-time train information
- SATSaNG — scheduling/network planning
- SFOORTI / FOIS — freight operations
- TMS — track management
- SMMS — signalling maintenance
- SIMS — safety information

The MVP should integrate only the data sources necessary for the demonstration.

---

## 3. Problem Statement

Current block planning involves significant officer judgment and manual analysis.

A block planner may need to consider:

- Safety impact
- Severity/security of the defect
- Operational impact
- Criticality
- Time sensitivity
- Existing failures or restrictions
- Whether multiple works can be combined
- Work dependencies
- Train movement and traffic
- Existing blocks and caution orders
- Historical disruptions
- Difference between planned and actual duration
- Weather conditions

This creates a complex decision-making process that can become highly dependent on officer experience.

### Proposed Solution

Use AI to analyze available historical and operational data and provide:

- Priority ranking
- Recommended block windows
- Conflict detection
- Dependency analysis
- Duration prediction
- Historical disruption analysis
- Weather-aware recommendations
- Automated report preparation
- Delay/failure analysis using NLP
- Anomaly alerts

---

# 4. Core Workflow

## Existing Concept

`Work Requirement → Officer Analysis → Priority → Block Planning → Execution → Reporting`

## Proposed AI-Assisted Workflow

`Work/Maintenance Request`
→ `Collect Data from COA/ROAMS/Authorized Sources`
→ `Validate and Normalize Data`
→ `Analyze Dependencies and Constraints`
→ `Analyze Train Movement and Existing Blocks`
→ `Analyze Historical MIS/PAM Data`
→ `Predict Actual Duration and Risk`
→ `Consider Weather`
→ `Calculate Priority`
→ `Recommend Block Window`
→ `Explain Recommendation`
→ `Officer Approves / Modifies / Rejects`
→ `Execution Monitoring`
→ `Actual Result Stored for Future Learning`

---

# 5. AI Modules

## 5.1 Intelligent Block Priority Selection

The AI should rank pending work based on the supplied priority criteria:

1. Safety impact
2. Security of the defect
3. Operational impact
4. Criticality
5. Time sensitivity
6. Existing failure/restrictions
7. Possibility of combining work

These factors are part of the supplied project workflow. fileciteturn0file0L2-L8

### AI Output

For every work item:

- Priority: High / Medium / Low
- Priority score
- Main reasons
- Historical evidence
- Risk level
- Confidence/uncertainty
- Recommended action

Example:

```text
PRIORITY: HIGH

Reasons:
• High safety impact
• Existing operational restriction
• Similar failures caused repeated disruption
• Can be combined with another planned work

Recommendation:
Schedule in the earliest feasible block window.
```

The recommendation must be explainable; AI should not provide an unexplained black-box score.

---

## 5.2 AI Block Scheduling

The scheduling engine should recommend feasible block windows by analyzing:

- Current and expected train movement
- Existing blocks
- Caution orders
- Work dependencies
- Location/section constraints
- Historical block duration
- Actual vs planned duration
- Operational impact
- Weather
- Possibility of combining work

Instead of assuming that:

`Planned Duration = Actual Duration`

the system should predict a realistic range:

`Historical Performance + Current Conditions → Expected Duration Range`

Example:

```text
Planned: 2 hours
Predicted: 2h 20m – 3h
Risk of extension: Medium
```

---

## 5.3 Work Dependency and Conflict Detection

The system should detect whether work activities are related or conflict with each other.

Possible dependencies:

- Sequential dependency
- Resource dependency
- Location dependency
- Safety dependency
- Operational dependency
- Equipment dependency
- Weather dependency
- Train movement dependency

The AI should also identify opportunities to combine compatible works into a single block.

Example:

```text
Conflict: Block B overlaps with Block A.

Suggestion:
1. Combine both works, OR
2. Move Block B to the next feasible window.
```

---

## 5.4 Historical Disruption Intelligence

Historical data from MIS/PAM and available operational records should be used to identify:

- Frequently disrupted sections
- Repeated failures
- Typical block durations
- Frequent extensions
- Common causes of delays
- Seasonal/weather-related patterns

Example:

```text
Historical Risk: HIGH

• Similar failure occurred 7 times recently
• Average recovery: 2h 40m
• Higher frequency during heavy rainfall
```

Historical data supports the recommendation; it should not automatically override officer judgment.

---

## 5.5 Weather Dependency

Weather can affect:

- Safety
- Work duration
- Feasibility of a block
- Probability of disruption

Relevant conditions may include heavy rain, flooding, storms, strong winds, extreme heat and poor visibility.

Example:

```text
Recommended block: 01:00–04:00
Weather risk increases after 04:30.

Recommendation:
Complete work before the high-risk period.
```

Weather is an input to the decision, not an automatic replacement for railway rules.

---

## 5.6 Train Scheduling Intelligence

Instead of creating a completely separate scheduling system, the AI should use authorized data from existing railway scheduling and movement systems.

Functions:

- Detect train/block conflicts
- Estimate operational impact
- Suggest alternative windows
- Predict possible knock-on delays
- Identify lower-disruption periods

---

## 5.7 MIS and PAM Automation

CCMIS already provides reports. The proposed AI enhancement focuses on reducing manual preparation and repetitive data entry.

### Proposed Flow

`Available System Data`
→ `Data Validation`
→ `Missing/Inconsistent Data Detection`
→ `Auto-population`
→ `AI-generated Summary`
→ `Officer Review`
→ `Final Report`

AI can:

- Collect available data automatically
- Detect missing fields
- Flag inconsistent entries
- Compare current and historical data
- Generate report summaries
- Highlight exceptions
- Prepare MIS/PAM drafts

The officer reviews the draft before it becomes official.

---

## 5.8 Delay Cause Analysis using NLP

Where delay, failure or unusual-event descriptions are available as text, NLP can extract:

- Cause
- Location
- Asset/component
- Severity
- Duration
- Operational impact
- Recurring patterns

Example:

```text
Input:
Train detained due to repeated signal failure near Section X.

AI:
Category: Signalling
Cause: Signal failure
Location: Section X
Recurring issue: Yes
```

The original text should remain available for verification.

---

## 5.9 Anomaly Detection

The system should detect unusual patterns such as:

- Blocks lasting significantly longer than expected
- Repeated failures at the same location
- Unexpected delays
- Frequent block extensions
- Sudden increases in unusual incidents
- Missing/stale operational data

Example:

```text
ALERT:
Block duration is 62% above the historical average.

Possible factors:
Weather / resource delay / extended work / operational restriction
```

Alerts require officer review; AI should not automatically take safety-critical action.

---

# 6. COA + ROAMS Integration

The proposed high-level flow is:

`ROAMS / Maintenance Information`
→ `Maintenance Requirement`
→ `AI Planning Layer`
← `COA Operational Data`
→ `Recommended Block`
→ `Officer Approval`

The objective is to reduce duplicate manual entry and allow maintenance requirements to be evaluated against actual operational conditions.

Before production, confirm:

- Available APIs
- Authentication
- Data ownership
- Data schemas
- Synchronization frequency
- Authorization
- Failure handling

---

# 7. System Architecture

```text
COA      ROAMS      Other Authorized Systems
 │         │                 │
 └─────────┴────────┬────────┘
                    ↓
            Integration Layer
                    ↓
          Data Validation Layer
                    ↓
             Unified Data Model
                    ↓
                AI Layer
       ┌────────────┼────────────┐
       ↓            ↓            ↓
    Priority    Scheduling     Anomaly
       ↓            ↓            ↓
   Historical    Duration       NLP
   Analysis     Prediction    Analysis
                    ↓
              Weather Input
                    ↓
             Officer Dashboard
                    ↓
       Approve / Modify / Reject
                    ↓
        Existing Operational Systems
```

A hybrid AI architecture is recommended:

- **Rule engine:** hard safety and operational constraints
- **ML models:** duration, risk and anomaly prediction
- **NLP:** delay/failure analysis
- **Optimization:** block window and work combination
- **LLM:** summaries and explanations

An LLM must not be the only mechanism making safety-critical recommendations.

---

# 8. Synthetic Data to Real Data

A major challenge is that synthetic hackathon data may not match real railway data.

Possible differences:

- Data format
- Missing values
- Terminology
- Data quality
- Update frequency
- Historical coverage
- Inter-system identifiers

### Proposed Transition

1. Build MVP using realistic synthetic data.
2. Test using authorized/anonymized historical data.
3. Run AI in shadow/read-only mode.
4. Compare AI recommendations with officer decisions and actual outcomes.
5. Conduct a limited pilot.
6. Scale gradually after validation.

The system should learn from **actual outcomes**, not blindly treat planned values as ground truth.

---

# 9. Division-Wide Adoption

The project refers to 68 divisions, while the supplied CCMIS manual states that centralized data was received from 69 divisions. The current official number should therefore be verified before deployment. fileciteturn1file0L40-L44

The design should support all divisions using:

- Common data model
- Configurable division-specific adapters
- Role-based access
- Central monitoring
- No separate codebase per division

## Adoption Strategy

Do not abruptly replace existing workflows:

`Existing System → AI Advisory Mode → Automate Repetitive Tasks → Controlled Pilot → Gradual Scale`

This allows officers to build trust and identify incorrect recommendations.

---

# 10. Security and Data Leakage

Railway operational data may be sensitive.

Required controls include:

- Role-based access control
- Least privilege
- Strong authentication
- Encryption in transit and at rest
- Secure APIs
- Audit logs
- Access monitoring
- Network segmentation
- Secrets management
- Backup and recovery
- AI/model access controls

Sensitive operational data must not be sent to unauthorized public AI services.

A specific **data-leak percentage should not be invented**. Leakage risk must be assessed through a formal threat model, security testing, vulnerability assessment and monitoring.

---

# 11. Human-in-the-Loop

The final workflow must preserve officer control:

`AI Recommendation → Explanation → Officer Review → Approve / Modify / Reject`

For each recommendation, show:

- What the AI recommends
- Why
- Relevant data/evidence
- Risk
- Confidence/uncertainty

Officer overrides should be logged to evaluate and improve the system.

---

# 12. Dashboard

The dashboard should focus on actionable information:

### Block Queue
- Pending work
- Priority
- Recommended window
- Risk

### Operational View
- Active blocks
- Caution orders
- Train movement
- Conflicts

### AI Insights
- Dependency warnings
- Historical disruption
- Duration prediction
- Weather risk
- Anomalies

### Reporting
- MIS/PAM drafts
- Missing data
- Exceptions
- Approval status

---

# 13. MVP Scope

The hackathon MVP should demonstrate:

1. COA-style operational data
2. ROAMS-style maintenance/work data
3. AI priority selection
4. Work dependency/conflict detection
5. Historical disruption analysis
6. Actual-duration prediction
7. Weather-aware planning
8. Recommended block window
9. Explainable recommendation
10. Officer approval workflow
11. MIS/PAM draft automation
12. NLP delay analysis
13. Anomaly alerts

## Demo Flow

`New Work Request`
→ `AI Priority`
→ `Dependency Check`
→ `Train/Block Conflict Check`
→ `Historical Risk`
→ `Duration Prediction`
→ `Weather Analysis`
→ `Recommended Block Window`
→ `Officer Approval`
→ `MIS/PAM Draft`

---

# 14. Out of Scope

The MVP should not claim:

- Full replacement of COA or ROAMS
- Autonomous train dispatch
- Autonomous safety decisions
- Automatic modification of live railway operations
- Integration with every CRIS system
- Production deployment across all divisions without validation

---

# 15. Key Questions Before Production

- What official COA and ROAMS APIs are available?
- Which maintenance data is relevant to block planning?
- Which MIS/PAM fields are currently manually entered?
- What are the official block-planning constraints?
- Which AI recommendations are permitted?
- What data is available for training and validation?
- What security standards are mandatory?
- What is the current official division count?
- How should the system behave if an upstream system fails?

---

# 16. Product Positioning

> **An AI-powered decision-support and automation layer for the existing Indian Railways control and maintenance ecosystem, focused on intelligent, explainable and officer-approved block planning.**

The project should emphasize one principle:

**Do not rebuild what already exists. Use existing systems as data and operational foundations, and add AI where human analysis, repetitive work and complex decision-making can be improved.**
