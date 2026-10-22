# BUV AI Evaluation Dashboard v2.0.0

## Purpose
The dashboard is a local decision-support workflow for evaluating a specific BUV AI service/use-case scope. It is designed for academic and professional use and separates four questions that are often incorrectly merged:

1. What may the user do now?
2. What BUV governance route applies?
3. What evidence and specialist reviews are required?
4. What institutional lifecycle decision has actually been recorded?

The platform does not auto-approve AI use and does not make a statutory legal classification.

## User journey
1. Define the real use case.
2. Enter context.
3. Enter data and impact.
4. Enter integration/autonomy.
5. Understand route and immediate action.
6. Complete proportionate evidence.
7. Complete triggered specialist reviews.
8. Record delegated decision.
9. Set Register status.
10. Set review and reassessment.

## Data model
The local Excel backend is `data/BUV_AI_Evaluation_Backend.xlsx`.

Core sheets:
- `AI_Register` — one row per assessed service/account/purpose/data/integration scope.
- `Assessment_Responses` — evidence against the 30 criteria.
- `Criteria_Master` — controlled evidence catalogue.
- `Decision_Log` — append-only governance decision history.
- `Dashboard` — Excel-side summary.
- `Lookups` — controlled values.
- `Migration_Notes` — design/change traceability.

## Operational safety
- Bind only to `127.0.0.1`.
- Do not expose the local service externally.
- Do not open the Excel backend while the dashboard is writing.
- Do not run multiple copies against the same backend.
- Backups are created before writes and retained according to `config/settings.json`.
- Logs deliberately omit prompts, evidence text and assessment content.

## Attribution
Solution design/build/deployment/implementation: Omar, 2026.
