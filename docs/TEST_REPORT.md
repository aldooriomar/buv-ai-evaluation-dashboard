# Test Report — BUV AI Evaluation Dashboard v2.0.0

Release date: 22 October 2026
Release type: Live-ready local controlled release
Solution design/build/deployment/implementation: Omar

## Result
PASS for the local controlled software release, subject to the institutional dependencies in `GO_LIVE_CHECKLIST.md`.

## Automated/static tests completed
- Python source compilation: PASS.
- Application self-test: PASS.
- Backend workbook structure: PASS; 30 criteria; 0 evaluations in distribution baseline.
- JavaScript syntax (`node --check`): PASS.
- Front-end DOM contract: PASS; every element ID referenced by `app.js` exists in `index.html`.
- Excel formula-error scan: PASS; no `#REF!`, `#DIV/0!`, `#VALUE!`, `#NAME?` or `#N/A` matches in the controlled workbook.
- Excel Dashboard render: PASS; numeric review-due KPI displays as an integer and operational-lane summary is readable.
- Active-package version scan: PASS; no v1.3.0 or v2.0.0-rc1 identifiers remain in active code/config/documentation.

## Decision-engine scenario tests
### Scenario A — public teaching exploration
Expected: GREEN + Safe Exploration only.
Result: PASS.
Operational lane: SAFE EXPLORATION.
Policy assurance: SAFE EXPLORATION ONLY — NOT PRODUCTION APPROVAL.
No specialist reviews automatically triggered by the bounded test facts.

### Scenario B — existing assured internal workflow
Expected: AMBER governance context + routine use inside existing approved scope, without duplicate review.
Result: PASS.
Operational lane: ROUTINE ASSURED USE.
Policy assurance: ROUTINE WITHIN EXISTING ASSURED SCOPE.
No duplicate specialist review automatically required when no material scope/high-impact trigger is present.

### Scenario C — student progression prediction
Expected: RED + formal assessment and specialist routing.
Result: PASS.
Operational lane: FORMAL ASSESSMENT.
Triggered reviews: ICT/Cybersecurity, Privacy/Legal, Academic/Professional and Procurement.
Decision guardrail test: PASS — a Pilot decision was rejected when triggered reviews were falsely marked Not required.
Evidence guardrail: PASS — positive decisions require all Required evidence criteria.
After valid review/evidence test data, a Pilot decision was recorded and the post-decision lane changed to CONTROLLED PILOT.

### Scenario D — unpublished research
Expected: RESEARCH CONFIDENTIALITY route with specialist review where triggered.
Result: PASS.
Operational lane: RESEARCH CONFIDENTIALITY.
The platform instructs use of an appropriately assured enterprise/API/research environment and warns against unmanaged consumer accounts for confidential BUV research.

## Data-layer tests
- Evaluation ID generation: PASS.
- Pre-write backup creation: PASS.
- Evidence rows and applicability persistence: PASS.
- Append-only decision log insertion: PASS.
- Timestamp/random-suffix Decision ID: PASS.
- Lifecycle status recalculation after decision: PASS.
- Review bypass prevention: PASS.

## Security/supportability checks
- Localhost-only configured binding: PASS.
- Request-size limit: configured.
- Local origin/host validation: configured.
- CSP, frame, MIME-sniff, referrer and permissions security headers: configured.
- Rotating system log: configured.
- Privacy-minimised audit log: configured.
- Diagnostics bundle intentionally excludes the Excel backend and assessment evidence: configured and code-reviewed.
- Windows bootstrap is ASCII-only with CRLF line endings to avoid the PowerShell 5.1 Unicode/parser defect seen in an earlier team package.

## Packaging limitation
The distributed bootstrap package does not contain the Windows Python runtime bytes. On first start it uses a bundled portable runtime if present, otherwise a compatible installed Python, otherwise it downloads the official CPython 3.13.15 embeddable runtime from python.org, verifies its fixed SHA-256 hash, and extracts it locally without Administrator rights. A BUV-managed runtime-embedded build can be created/distributed by ICT where internet access is blocked.

## Institutional release limitation
The bundled BUV AI Usage Guideline v3.0 and ICT AI Technology Use Policy 2026 are final drafts pending formal BUV approval. This is an explicit institutional dependency, not a software defect. The UI displays this status.

## Governance-source and benchmark verification
- BUV v3.0 draft source status displayed in product: PASS.
- 15-working-day target implemented as escalation, not deemed/default approval: PASS.
- Safe Exploration separated from institutional approval: PASS.
- Pseudonymisation/masking not treated as automatic anonymisation: PASS.
- Research Confidentiality route avoids consumer-account safe-harbour logic: PASS.
- Specialist decision rights remain separated from ICT technical assurance: PASS.
- External benchmark claims are advisory only; unsupported universal approval timelines/job titles are not hard-coded: PASS.
- ISO references are presented as alignment/design references and not as a certification claim: PASS.

## Release packaging acceptance criteria
The final release ZIP must pass all of the following after creation and fresh extraction:
- ZIP archive integrity test.
- Application self-test from the extracted copy.
- JavaScript syntax validation from the extracted copy.
- Immutable-file SHA-256 manifest verification.
- ASCII-only Windows bootstrap script check and CRLF line-ending check.
- Clean distribution baseline: 30 criteria and 0 evaluations.
- No Python bytecode/cache artefacts in the distributed application.
- Mutable logs and backup data excluded from the immutable checksum manifest.

Final packaging verification results are recorded in `RELEASE_NOTES_v2.0.0.txt` beside the release ZIP.

## Final package verification — 22 October 2026
Pre-release archive verification completed from a clean extraction:
- ZIP archive integrity: PASS (no corrupt entry detected).
- Extracted application self-test: PASS — v2.0.0, 30 criteria, 0 evaluations.
- Extracted JavaScript syntax validation: PASS.
- Immutable-file checksum verification: PASS — 34 files checked, 0 mismatches.
- Windows bootstrap and launcher encoding: PASS — ASCII-only and CRLF line endings.
- Python cache/bytecode artefacts in distribution: PASS — none present.

The release was rebuilt after recording these results and subjected to the same final verification gate before publication.
