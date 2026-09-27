# Legal Test Docs

Shared test fixtures for the legal-document experiments in this repository.
Everything here is fictional; the documents contain deliberate problems for
tools and plugins to find. This folder is not a product and has no code.

## `test-msa.docx`

A one-page Master Services Agreement (Acme Corporation and Widget Consulting
LLC, effective January 1, 2025): a title plus five numbered sections (Services,
Confidential Information, Intellectual Property, Dispute Resolution, Term and
Termination). No tables. Useful for:

- **Find and replace / clause remediation** — Section 4 requires arbitration
  under the AAA "Commercial Arbitration Rules (2013 edition)", the scenario the
  Clause Remediation App updates.
- **Bracketed placeholders** — `[City]`, `[State]` in Section 4.
- **Defined-term extraction** — quoted definitions ("Agreement", "Effective
  Date", "Company", "Service Provider", "SOW", "Confidential Information",
  "Intellectual Property Rights", "Initial Term") and capitalized terms used
  without a definition (Deliverables, Receiving Party, Disclosing Party,
  Pre-Existing Materials, Governing Law).

Note: the defined terms are wrapped in both straight and curly quotes
(`"“Agreement”"`), which exercises quote handling in term extraction.

## `employment/`

Markdown fixtures for testing an employment-law plugin. See
[`employment/TEST-GUIDE.md`](employment/TEST-GUIDE.md) for the skill each file
targets and the full list of embedded issues.

| File | Document | Main issues planted |
| --- | --- | --- |
| `offer-letter-sarah-chen.md` | Offer letter | California non-compete, choice of law, overbroad invention assignment, wage/hour exposure |
| `termination-memo-david-park.md` | Termination recommendation memo | FMLA and complaint retaliation risk, pending accommodation, age, short PIP |
| `employee-handbook-acme.md` | Employee handbook | PTO forfeiture and payout, arbitration and class waiver, NLRA social media, missing lactation policy |
| `contractor-sow-martinez.md` | Contractor statement of work | Worker misclassification indicators (set hours, equipment, exclusivity) |
| `investigation-intake-thompson.md` | Harassment investigation intake | Quid pro quo pattern, retaliation, interim measures, evidence preservation |
| `leave-register-seed.md` | Leave register | Unanswered accommodation and leave requests, USERRA, workers' comp restrictions |
| `handbook-proposed-changes.md` | Proposed handbook changes | Use-it-or-lose-it PTO, charge-filing waiver, NLRA, expense reimbursement |
| `TEST-GUIDE.md` | Test guide | Answer key for the files above |
