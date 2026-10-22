# Governance Design Basis

## Controlled BUV source basis
The decision engine is derived from the bundled current source drafts:
- BUV AI Usage Guideline v3.0 — Final Draft for Committee Approval.
- BUV ICT AI Technology Use Policy 2026 — Final uplifted draft for institutional review and approval.

The software deliberately does not treat these drafts as formally approved until BUV completes its authorised governance process.

### Material corrections carried into v2.0.0
- A missed 15-working-day assessment target triggers escalation; it does not create automatic or deemed approval.
- Safe Exploration is narrow: public/synthetic/appropriately authorised non-sensitive data, no BUV-system integration, and no controlled-data/production approval.
- Pseudonymisation/masking is not treated as anonymisation where re-identification remains reasonably possible.
- Confidential research is routed to an appropriately assured enterprise/API/managed research environment; unmanaged consumer accounts are not the default control.
- ICT provides technical/security assurance; academic, privacy/legal, research/ethics, procurement and delegated risk owners retain their own decision rights.
- An existing BUV-assured service used within its documented scope is not repeatedly re-assessed merely because the approved scope contains Internal or authorised basic personal data. Material scope changes/high-impact triggers cause reassessment.
- Legacy spreadsheet numeric totals are not used as automatic Approve/Reject logic. Evidence is used to support accountable human decisions.

## External research and benchmark basis
External research was used to challenge and improve the implementation, not to replace BUV governance.

- ISO/IEC 42001:2023 — AI management systems: https://www.iso.org/standard/42001
- ISO/IEC 42005:2025 — AI system impact assessment: https://www.iso.org/standard/42005
- NIST AI Risk Management Framework: https://www.nist.gov/itl/ai-risk-management-framework
- University of Oxford generative AI tools/policy guidance: https://www.ox.ac.uk/about/digital/gen-ai/gen-ai-tools-policy-guidance
- University of Cambridge data-protection AI guidance: https://www.information-compliance.admin.cam.ac.uk/data-protection/guidance/ai-guidance
- EDUCAUSE higher-education AI governance discussions: https://www.educause.edu/
- Official Vietnamese legal portal: https://vanban.chinhphu.vn/

These sources support a risk-based, lifecycle, human-accountability and cross-functional governance model rather than one universal AI score.

## Meaning of the four BUV routes in the software
- GREEN — low-control route for routine/public/non-sensitive use. It is not a universal approval badge.
- AMBER — proportionate local control, typically non-public information, authorised basic personal data in an assured scope, or human-reviewed decision support.
- RED — prior formal review before deployment/controlled-data use where impact, sensitivity, integration, autonomy or regulatory trigger warrants it.
- RESEARCH CONFIDENTIALITY — protected route for unpublished/proprietary/patent/NDA-bound research; specialist review applies when triggered.

## Legal screening
The high-impact field asks for factual characteristics (for example learner ranking/monitoring or consequential decisions). The platform routes a possible trigger to Privacy/Legal; it does not claim that an internal colour equals statutory classification.

## Claims deliberately not encoded as automatic rules
The platform does not reproduce every statement in the 2026 governance-review infographic as a hard rule. The infographic is a useful review aid, but the controlled v3.0 Guideline and 2026 ICT Policy drafts remain the direct BUV source basis for the decision engine.

- No universal "3-5 week global benchmark" is encoded. External university practice varies by service, risk, procurement, data and local governance. BUV retains its own 15-working-day target for initial technical/security assessment, with escalation rather than automatic approval when the target is exceeded.
- No fixed job title such as "Chief Privacy Officer" is hard-coded as the only valid privacy authority. The software routes to the BUV Privacy/Data Protection and Legal function so BUV can apply its approved organisational role names.
- ISO/IEC references are used as design and assurance references. They do not state or imply that BUV, this software or any evaluated service is ISO certified.
- A GREEN route does not mean "BUV Approved". GREEN describes the governance route for the stated use case. Service assurance and institutional lifecycle status are shown separately.
- RED does not automatically mean "Reject". It means stop before deployment or controlled-data use until the triggered evidence and authorised reviews are complete. The authorised owner may subsequently approve, condition, pilot, restrict or reject the use within delegated authority.
- RESEARCH CONFIDENTIALITY is not a loophole around privacy, ethics, contract or security requirements. Those specialist reviews are triggered when the facts require them.

## External benchmark observations checked for this release
External benchmarking checked on 22 October 2026 supports the direction of the design rather than a single universal university workflow:

- ISO/IEC 42001:2023 treats responsible AI governance as a management system requiring establishment, implementation, maintenance and continual improvement.
- ISO/IEC 42005:2025 treats AI impact assessment as a lifecycle activity that should be revisited as the system or context changes.
- Oxford provides institutionally managed enterprise AI services with secure sign-on and university-wide policy/guidance, while retaining local academic guidance and specialist governance.
- Cambridge's current information-compliance guidance emphasises licensed tools, caution with personal/sensitive data and meaningful human involvement where AI supports decisions about people.
- EDUCAUSE's 2026 higher-education discussions emphasise cross-functional, scalable governance and governance that supports institutional adoption rather than reducing the problem to an IT purchase approval.

These observations are used to test the reasonableness of BUV's model. They do not create BUV policy or override Vietnamese law or authorised BUV decision rights.

## Automation boundary
The dashboard automates repeatable administrative logic: intake completeness, route calculation, evidence applicability, specialist-review routing, lifecycle status, due/review prompts, escalation cues and record keeping. It deliberately does not automate legal conclusions, academic merit, research-ethics determinations, privacy lawfulness, procurement authority, residual-risk acceptance or the final delegated institutional decision.

This boundary is intentional. It makes the platform useful without turning a colour, numerical score or software rule into an institutional authority it does not possess.
