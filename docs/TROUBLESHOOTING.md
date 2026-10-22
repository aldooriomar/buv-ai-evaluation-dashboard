# Troubleshooting

## Dashboard does not start
1. Ensure the ZIP was fully extracted.
2. Run only `RUN_BUV_AI_DASHBOARD.bat`.
3. Keep the black window open and read the first ERROR line.
4. Check `logs/system.log` after a run attempt.

## Python download is blocked
The first start only needs python.org when there is no portable or compatible Python runtime. Ask BUV ICT/platform owner for an approved runtime-embedded package rather than bypassing endpoint/security controls.

## Excel backend is locked
Close `data/BUV_AI_Evaluation_Backend.xlsx` in Excel and retry.

## Port 8765 already in use
Close the other BUV AI Dashboard instance. v2.0.0 intentionally does not choose a second port because two instances must not write one Excel backend concurrently.

## Browser does not open automatically
Open `http://127.0.0.1:8765/` manually while the startup window remains running.

## A save fails
Check the visible error first, then `logs/system.log`. The audit log intentionally records only event metadata, not assessment content.

## Need to share diagnostics
Use Policy & Guidance > Diagnostics ZIP. It excludes the Excel backend and assessment evidence.
