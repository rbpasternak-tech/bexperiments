# Employment Legal Plugin — Test Guide

All docs are fictional. Each contains intentional issues for the plugin to catch.

## Documents and What to Test

### 1. offer-letter-sarah-chen.md
**Skill:** `/employment-legal:hiring-review`
**Embedded Issues:**
- 24-month non-compete with nationwide scope — unenforceable in California (where she lives)
- Texas choice-of-law clause for a CA-resident employee — conflict of laws problem
- "All inventions" assignment clause covers work outside business hours — likely overbroad, conflicts with CA Labor Code 2870
- Exempt classification with 50-55 hour expectation stated in writing — potential wage/hour exposure
- Credit check in background check — restricted in some jurisdictions without specific job justification
- 24-month signing bonus clawback — aggressive, potentially unenforceable depending on state

### 2. termination-memo-david-park.md
**Skill:** `/employment-legal:termination-review`
**Embedded Issues:**
- FMLA leave 6 weeks before PIP started — temporal proximity creates retaliation inference
- Internal complaint about manager's FMLA-related comments 5 weeks before PIP — retaliation risk
- Pending reasonable accommodation request with no response — cannot terminate during interactive process
- Employee is 58 in a team where next oldest is 34 — age discrimination risk (ADEA)
- Only 30-day PIP (handbook says 60-90 days) — deviation from own policy
- 21-day release consideration period — correct for individual, but should be 45 days if part of group/RIF (need to check)
- PTO payout denied per handbook for involuntary terms — potentially illegal in California
- Severance is thin (2 weeks for 14 months) with no COBRA subsidy
- Sparse documentation in early performance period (verbal only, no written record)

### 3. employee-handbook-acme.md
**Skill:** `/employment-legal:cold-start-interview` (feed this during setup)
**Embedded Issues:**
- PTO forfeiture on carry-over > 5 days — illegal in California (earned wage)
- PTO not paid out on involuntary termination — illegal in CA, potentially other states
- Exempt salary deductions for partial-day sick leave after exhaustion — FLSA risk
- Mandatory arbitration with class action waiver — enforceable but aggressive; may not survive state-specific challenges
- Benefits start after 60 days — not an error but worth flagging for competitiveness
- Anti-harassment policy lacks specific reporting channels, investigation timeline, or trained investigator requirement
- Social media policy may chill NLRA Section 7 protected concerted activity
- No lactation accommodation policy (PUMP Act gap)
- No state-specific supplements for CA, NY, or other states with unique requirements

### 4. contractor-sow-martinez.md
**Skill:** `/employment-legal:worker-classification`
**Embedded Issues:**
- Set hours (9-5, M-F) — behavioral control indicator
- Required 3 days/week in-office — behavioral control
- Company-provided equipment (laptop, monitor, tools) — financial control indicator
- Company email address — integration into business
- Daily standups + sprint planning + quarterly reviews — behavioral control
- 40 hours/week expected — full-time equivalent
- Exclusivity clause — strong misclassification indicator
- Manager sets priorities — right to direct work
- "Work for hire" IP assignment — may not be valid for non-employees in all categories
- Would likely fail ABC test (CA), economic reality test (federal), and common law test

### 5. investigation-intake-thompson.md
**Skill:** `/employment-legal:investigation-open` then `investigation-add`
**Embedded Issues:**
- Pattern escalation: social comments → closed-door quid pro quo → after-hours contact → adverse action
- Potential quid pro quo harassment (Incident 2)
- Potential retaliation (campaign reassignment after rejection)
- Subject reports directly to CEO — escalation path complexity
- Former employee (Katie Lin) may be relevant witness — departed without exit interview follow-up
- Complainant wants confidentiality but subject must eventually be interviewed — tension to manage
- Interim measures needed (reporting structure change) — time-sensitive
- Evidence preservation needed (Slack messages) — IT hold required immediately

### 6. leave-register-seed.md
**Skill:** `/employment-legal:leave-tracker` and `/employment-legal:log-leave`
**Embedded Issues:**
- David Park: Pending accommodation request (53+ days no response) + active termination recommendation during FMLA/accommodation
- Rachel Kim: Unanswered extension request; complex NY PFL + FMLA + company leave stacking calculation
- Marcus Williams: Manager wants to permanently fill territory — USERRA reemployment rights violation
- Linda Chen: 53 days with no response to ADA accommodation documentation; manager making inaccurate statements to team; two unanswered employee emails
- James Morrison: Supervisor assigning tasks exceeding medical restrictions — workers' comp retaliation risk

### 7. handbook-proposed-changes.md
**Skill:** `/employment-legal:handbook-updates`
**Embedded Issues:**
- Change 1 (PTO): Use-it-or-lose-it is illegal in California (earned wage doctrine); problematic in other states
- Change 2 (Remote): Forcing remote-hire relocation or elimination is mass-layoff risk (WARN Act if enough people); ADA accommodation conflicts (Linda Chen); potential constructive discharge
- Change 3 (Arbitration): Cannot waive right to file EEOC/NLRB/OSHA charges — flatly illegal
- Change 4 (Social Media): Banning negative comments about working conditions violates NLRA Section 7; "immediate termination" removes progressive discipline
- Change 5 (Expenses): 14-day hard cutoff for reimbursement may violate CA Labor Code 2802 and similar state laws
- Change 6 (Lactation): Generally good but "coordinate with manager to minimize disruption" language could chill usage; should reference PUMP Act compliance; may need to specify frequency/duration protections
