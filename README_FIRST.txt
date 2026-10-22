BUV AI EVALUATION DASHBOARD v2.0.0
LIVE-READY LOCAL CONTROLLED RELEASE

FOR COMMITTEE MEMBERS / REVIEWERS

1. Right-click the ZIP file and choose Extract All.
2. Open the extracted folder.
3. Double-click RUN_BUV_AI_DASHBOARD.bat.
4. Keep the black startup window open while using the dashboard.
5. Your default browser opens http://127.0.0.1:8765/

Do not run the platform from inside the ZIP.
Do not open data\BUV_AI_Evaluation_Backend.xlsx in Excel while the dashboard is saving.
Do not share one Excel backend between multiple running dashboard instances.

FIRST START / NO ADMIN RIGHTS
The launcher first uses a portable python.exe if one is already in the dashboard folder. If none is present, it uses a compatible existing Python installation where available. Otherwise it downloads the official Python 3.13.15 embeddable Windows runtime from python.org, verifies the fixed SHA-256 hash, and extracts it into this folder only. It does not install Python into Windows and does not need Administrator rights.

If your organisation blocks python.org and no compatible Python exists, ask the BUV AI platform owner / ICT for an approved runtime-embedded copy.

WHAT THIS PLATFORM DOES
- Guides a reviewer through a 10-step BUV AI evaluation.
- Answers "What may happen now?" before showing the governance colour.
- Distinguishes Safe Exploration, routine assured use, formal assessment and Research Confidentiality.
- Applies GREEN / AMBER / RED / RESEARCH CONFIDENTIALITY as governance routes, not approval labels.
- Makes evidence requirements proportionate to the actual use case.
- Routes triggered specialist reviews to the right BUV functions.
- Records the delegated institutional decision, lifecycle status, conditions and review date.
- Uses an Excel workbook as the local backend and creates rolling backups before writes.
- Writes privacy-minimised technical/audit logs to the logs folder.
- Does not call an external AI API and does not send assessment content outside localhost.

IMPORTANT GOVERNANCE STATUS
The bundled BUV AI Usage Guideline v3.0 and BUV ICT AI Technology Use Policy 2026 are final drafts pending formal institutional approval. This software is live-ready decision support; it does not make those source drafts approved policy and does not replace authorised BUV decision-makers.

DEPLOYMENT LIMIT
This package is designed for one local user/copy at a time. For a future central multi-user production service, use a managed server, authentication/roles, central database, concurrency controls and institutional backup/monitoring.

Solution design/build/deployment/implementation: Omar, 2026
Documentation language: English (UK)
