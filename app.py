from __future__ import annotations

# Solution design/build/deployment/implementation: Omar, 2026
# Local/offline BUV AI governance decision-support platform.

import io
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import secrets
import shutil
import sys
import threading
import webbrowser
import zipfile
from datetime import date, datetime, timedelta
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
from xlsx_store import XlsxDatabase, validate_xlsx


def _load_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


SETTINGS = _load_json(ROOT / "config" / "settings.json", {})
APP_CFG = SETTINGS.get("application", {})
SERVER_CFG = SETTINGS.get("server", {})
BACKUP_CFG = SETTINGS.get("backup", {})
LOG_CFG = SETTINGS.get("logging", {})
ASSESS_CFG = SETTINGS.get("assessment", {})
GOVERNANCE_SOURCES = _load_json(ROOT / "config" / "governance_sources.json", {})
HOLIDAY_CFG = _load_json(ROOT / "config" / "holidays.json", {})

APP_VERSION = str(APP_CFG.get("version") or "2.0.0")
RELEASE_LABEL = str(APP_CFG.get("release_label") or "Live-ready local release")
DATA_FILE = ROOT / "data" / "BUV_AI_Evaluation_Backend.xlsx"
LOCK = threading.RLock()
HOST = str(SERVER_CFG.get("host") or "127.0.0.1")
PORT = int(os.environ.get("BUV_AI_DASHBOARD_PORT", str(SERVER_CFG.get("port") or 8765)))
MAX_REQUEST_BYTES = int(SERVER_CFG.get("max_request_bytes") or 1048576)
BACKUP_DIR = ROOT / "data" / "backups"
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

REGISTER_SHEET = "AI_Register"
RESPONSES_SHEET = "Assessment_Responses"
CRITERIA_SHEET = "Criteria_Master"
DECISION_SHEET = "Decision_Log"

RATING_SCORE = {"Low": 1, "Medium": 2, "High": 3, "N/A": None, "Not assessed": None, "": None, None: None}
BACKUP_RETAIN = int(BACKUP_CFG.get("retain") or 20)
ASSESSMENT_TARGET_DAYS = int(ASSESS_CFG.get("target_working_days") or 15)
REVIEW_DUE_DAYS = int(ASSESS_CFG.get("review_due_days") or 30)

SYSTEM_LOG = logging.getLogger("buv.system")
SYSTEM_LOG.setLevel(logging.INFO)
if not SYSTEM_LOG.handlers:
    fh = RotatingFileHandler(LOG_DIR / "system.log", maxBytes=int(LOG_CFG.get("max_bytes") or 2097152), backupCount=int(LOG_CFG.get("backup_count") or 5), encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    SYSTEM_LOG.addHandler(fh)

AUDIT_LOG = LOG_DIR / "audit.jsonl"

def audit_event(event: str, **fields):
    # Privacy-minimised event log: no prompts, evidence text, personal data or assessment content.
    row = {"ts": datetime.now().isoformat(timespec="seconds"), "event": event, "version": APP_VERSION}
    for k, v in fields.items():
        if v not in (None, ""):
            row[k] = str(v)[:240]
    try:
        with AUDIT_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        SYSTEM_LOG.exception("audit_write_failed")

BLUEPRINT_STEPS = [
    {"step": 1, "title": "Define the real use case", "short": "Use case", "description": "Name the exact service/account and state the bounded BUV purpose. Assess the real configuration, not a vendor brand in the abstract."},
    {"step": 2, "title": "Enter context", "short": "Context", "description": "Record the accountable owner, requesting unit, users, scale, existing assurance scope and complete-request date."},
    {"step": 3, "title": "Enter data and impact", "short": "Data & impact", "description": "Identify information sensitivity, personal-data status, research/assessment/ethics/contract triggers and how much the AI can influence people or BUV outcomes."},
    {"step": 4, "title": "Enter integration / autonomy", "short": "Integration", "description": "Record BUV-system access, permissions, autonomous actions and procurement route. The platform then creates the governed scope record."},
    {"step": 5, "title": "Understand route & immediate action", "short": "Action & route", "description": "First see what may happen now, what must stop and who acts next. GREEN / AMBER / RED / RESEARCH CONFIDENTIALITY is supporting governance context, not approval."},
    {"step": 6, "title": "Complete proportionate evidence", "short": "Evidence", "description": "Complete the criteria marked Required for this use case. Recommended items add assurance; Not in scope items do not create paperwork."},
    {"step": 7, "title": "Complete triggered specialist reviews", "short": "Reviews", "description": "Record only the specialist reviews triggered by the facts: ICT/Cybersecurity, Privacy/Legal, Academic/Professional, Research/Ethics and Procurement."},
    {"step": 8, "title": "Record delegated decision", "short": "Decision", "description": "The authorised BUV decision owner records Approve, Conditional, Pilot, Reject, Suspend or Retire with rationale. The platform never auto-approves."},
    {"step": 9, "title": "Set Register status", "short": "Register", "description": "Translate the recorded decision into the BUV AI Services Register lifecycle status, conditions and residual-risk ownership where applicable."},
    {"step": 10, "title": "Set review & reassessment", "short": "Review", "description": "Record review/expiry and change triggers, confirm the final action summary, then append the auditable decision record to Excel."},
]

SCENARIO_STARTERS = [
    {
        "id": "green_teaching",
        "name": "GREEN example — published literature",
        "summary": "Lecturer explores a new AI literature assistant using published sources only.",
        "record": {
            "Tool / Service": "ExampleAI Literature Assistant", "Provider": "Example Vendor", "Account / Tenant": "Individual evaluation account",
            "Purpose Domain": "Teaching & Learning", "Primary Use Case": "Summarise published journal articles and public sources for lesson preparation. The lecturer independently verifies material outputs before use.",
            "Requesting Unit": "School / Programme Team", "Sponsor / AI System Owner": "Dr Test Owner", "User Group": "Faculty", "Intended Scale": "Individual / Exploration",
            "Existing Assurance Scope": "New / Unassessed service or scope", "Data Classification": "Public", "Personal Data": "None", "Research Confidentiality": "No",
            "Secure Assessment Content": "No", "Human Participants / Ethics": "No", "NDA / Contractual Restrictions": "No", "Decision Impact": "No material effect",
            "System Integration": "None", "Autonomous Actions": "No", "Procurement Type": "No procurement / exploration", "Statutory High-Risk": "No known trigger after factual screening"
        }
    },
    {
        "id": "amber_admin",
        "name": "AMBER example — internal meeting notes",
        "summary": "Assured enterprise AI summarises non-public departmental notes; a staff member approves the final actions.",
        "record": {
            "Tool / Service": "BUV-assured enterprise AI service", "Provider": "Existing enterprise provider", "Account / Tenant": "BUV enterprise tenant",
            "Purpose Domain": "Professional Services", "Primary Use Case": "Summarise internal departmental meeting notes and draft an action list. An authorised staff member reviews and approves all final actions.",
            "Requesting Unit": "Professional Services", "Sponsor / AI System Owner": "Department Process Owner", "User Group": "Professional Staff", "Intended Scale": "Team / Department",
            "Existing Assurance Scope": "Existing BUV-assured service within approved scope", "Data Classification": "Internal", "Personal Data": "Basic / Ordinary identifiable", "Research Confidentiality": "No",
            "Secure Assessment Content": "No", "Human Participants / Ethics": "No", "NDA / Contractual Restrictions": "No", "Decision Impact": "Human-reviewed decision support",
            "System Integration": "None", "Autonomous Actions": "No", "Procurement Type": "Existing enterprise service", "Statutory High-Risk": "No known trigger after factual screening"
        }
    },
    {
        "id": "red_student",
        "name": "RED example — student progression prediction",
        "summary": "AI ranks students for progression-risk intervention using student records and academic performance.",
        "record": {
            "Tool / Service": "Student Success Prediction AI", "Provider": "Example Analytics Provider", "Account / Tenant": "Proposed BUV institutional tenant",
            "Purpose Domain": "Student Support", "Primary Use Case": "Analyse student records, attendance and academic performance to predict progression risk and rank students for intervention.",
            "Requesting Unit": "Student Services / Academic Team", "Sponsor / AI System Owner": "Student Success Process Owner", "User Group": "Mixed", "Intended Scale": "School / Function",
            "Existing Assurance Scope": "New / Unassessed service or scope", "Data Classification": "Restricted", "Personal Data": "Large-scale / Systematic", "Research Confidentiality": "No",
            "Secure Assessment Content": "No", "Human Participants / Ethics": "No", "NDA / Contractual Restrictions": "Yes", "Decision Impact": "Material / consequential decision",
            "System Integration": "Read-only / low privilege", "Autonomous Actions": "No", "Procurement Type": "Paid institutional service", "Statutory High-Risk": "Possible — automated learner testing/evaluation/ranking"
        }
    },
    {
        "id": "research_confidential",
        "name": "RESEARCH example — unpublished manuscript",
        "summary": "Researcher evaluates AI on unpublished, potentially patentable or NDA-bound material.",
        "record": {
            "Tool / Service": "Assured Research AI Environment", "Provider": "Example Research AI Provider", "Account / Tenant": "Managed research environment",
            "Purpose Domain": "Research", "Primary Use Case": "Support analysis and drafting of an unpublished research manuscript containing potentially patentable methods and confidential research information.",
            "Requesting Unit": "Research Team", "Sponsor / AI System Owner": "Principal Investigator", "User Group": "Researchers", "Intended Scale": "Team / Department",
            "Existing Assurance Scope": "New / Unassessed service or scope", "Data Classification": "Confidential", "Personal Data": "None", "Research Confidentiality": "Yes",
            "Secure Assessment Content": "No", "Human Participants / Ethics": "No", "NDA / Contractual Restrictions": "Yes", "Decision Impact": "No material effect",
            "System Integration": "None", "Autonomous Actions": "No", "Procurement Type": "Departmental pilot", "Statutory High-Risk": "No known trigger after factual screening"
        }
    },
]


def serialise(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def backup_workbook():
    """Create a rolling local backup before a web save."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    target = BACKUP_DIR / f"BUV_AI_Evaluation_Backend_{stamp}.xlsx"
    shutil.copy2(DATA_FILE, target)
    backups = sorted(BACKUP_DIR.glob("BUV_AI_Evaluation_Backend_*.xlsx"), key=lambda x: x.stat().st_mtime, reverse=True)
    for old in backups[BACKUP_RETAIN:]:
        try:
            old.unlink()
        except OSError:
            pass


def load_records():
    if not DATA_FILE.exists():
        raise FileNotFoundError(DATA_FILE)
    with LOCK:
        db = XlsxDatabase(DATA_FILE)
        register = db.records(REGISTER_SHEET)
        responses = db.records(RESPONSES_SHEET)
        criteria = db.records(CRITERIA_SHEET)
        decisions = db.records(DECISION_SHEET)
        return register, responses, criteria, decisions


def normalise_text(v):
    return "" if v is None else str(v).strip()


def is_unknown(value):
    return normalise_text(value) in {"", "Unknown"}


def _value(record, key):
    return normalise_text(record.get(key))


def _personal_kind(record):
    return _value(record, "Personal Data")


def compute_pathway_details(record):
    """Calculate the BUV staff-facing governance route, not an approval or legal classification."""
    research = _value(record, "Research Confidentiality") == "Yes"
    data_class = _value(record, "Data Classification")
    personal = _personal_kind(record)
    impact = _value(record, "Decision Impact")
    integration = _value(record, "System Integration")
    autonomy = _value(record, "Autonomous Actions")
    high_risk = _value(record, "Statutory High-Risk")
    scale = _value(record, "Intended Scale")
    secure_assessment = _value(record, "Secure Assessment Content")
    existing = _value(record, "Existing Assurance Scope")

    red, amber, research_reasons = [], [], []
    if personal in {"Sensitive / Special", "Large-scale / Systematic"}:
        red.append("sensitive or large-scale personal data")
    if secure_assessment == "Yes - live / secure assessment":
        red.append("live or secure assessment material")
    if impact == "Material / consequential decision":
        red.append("AI materially drives a consequential decision")
    if integration in {"Write / action capability", "Privileged / broad access"}:
        red.append("write/action or privileged BUV-system integration")
    if autonomy in {"Limited with human confirmation", "Yes - consequential actions"}:
        red.append("AI can take actions, not only advise")
    if high_risk.startswith("Possible") or high_risk in {"Legal review confirms high-risk", "Unknown — Legal review required", "Unknown - Legal review required"}:
        red.append("factual screening indicates a possible statutory/high-impact trigger")
    if scale == "Institution-wide":
        red.append("institution-wide deployment")

    if data_class in {"Internal", "Confidential", "Restricted"}:
        amber.append("non-public BUV information")
    if personal in {"Pseudonymised / masked", "Basic / Ordinary identifiable", "Basic / Ordinary"}:
        amber.append("personal data requiring proportionate controls")
    if impact == "Human-reviewed decision support":
        amber.append("AI informs a decision subject to meaningful human review")
    if integration == "Read-only / low privilege":
        amber.append("read-only or low-privilege integration")
    if scale in {"Team / Department", "Pilot Cohort", "School / Function"}:
        amber.append("departmental, pilot or School/function workflow")
    if secure_assessment == "Draft / non-secure only":
        amber.append("assessment-related material requiring local control")
    if existing in {"Existing service — new/expanded use", "Conditional / Pilot scope"}:
        amber.append("new/expanded or conditional service scope")

    if research:
        research_reasons.append("unpublished, proprietary, patent or NDA-bound research route selected")

    core_fields = {
        "Data classification": data_class,
        "Personal-data status": personal,
        "Research confidentiality": _value(record, "Research Confidentiality"),
        "Decision impact": impact,
        "System integration": integration,
        "Autonomous actions": autonomy,
        "Deployment scale": scale,
        "High-impact factual screening": high_risk,
        "Assessment security": secure_assessment,
    }
    unknowns = [label for label, value in core_fields.items() if is_unknown(value)]

    if research and red:
        pathway = "RED + RESEARCH CONFIDENTIALITY"
    elif red:
        pathway = "RED"
    elif research:
        pathway = "RESEARCH CONFIDENTIALITY"
    elif amber:
        pathway = "AMBER"
    elif unknowns:
        pathway = "UNDETERMINED"
    else:
        pathway = "GREEN"

    reasons = red + research_reasons + amber
    if unknowns:
        reasons.append("information still required: " + ", ".join(unknowns))
    if not reasons:
        reasons.append("public/non-sensitive use with no material decision, system integration or autonomous action identified")
    return {"pathway": pathway, "reasons": reasons, "provisional": bool(unknowns), "unknowns": unknowns}


def compute_pathway(record):
    return compute_pathway_details(record)["pathway"]


def safe_exploration_status(record):
    status = _value(record, "Register Status")
    if status in {"BUV Provided / Assured", "Conditional", "Pilot", "Restricted", "Suspended", "Retired"}:
        return f"NOT APPLICABLE — REGISTER STATUS: {status}"
    existing = _value(record, "Existing Assurance Scope")
    if existing == "Existing BUV-assured service within approved scope":
        return "NOT APPLICABLE — EXISTING ASSURED SCOPE"

    required = ["Data Classification", "Personal Data", "Research Confidentiality", "Decision Impact", "System Integration", "Autonomous Actions", "Intended Scale", "Statutory High-Risk", "Secure Assessment Content", "Human Participants / Ethics", "NDA / Contractual Restrictions", "Procurement Type"]
    if any(is_unknown(record.get(k)) for k in required):
        return "INFORMATION REQUIRED"

    personal = _personal_kind(record)
    no_personal = personal in {"None", "Fully anonymised under approved criteria"}
    high_risk = _value(record, "Statutory High-Risk")
    eligible = (
        existing == "New / Unassessed service or scope"
        and _value(record, "Data Classification") == "Public"
        and no_personal
        and _value(record, "Research Confidentiality") == "No"
        and _value(record, "Decision Impact") == "No material effect"
        and _value(record, "System Integration") == "None"
        and _value(record, "Autonomous Actions") == "No"
        and _value(record, "Intended Scale") == "Individual / Exploration"
        and high_risk.startswith("No known trigger")
        and _value(record, "Secure Assessment Content") == "No"
        and _value(record, "Human Participants / Ethics") == "No"
        and _value(record, "NDA / Contractual Restrictions") == "No"
        and _value(record, "Procurement Type") in {"No procurement / exploration", "Free / individual account"}
    )
    return "ELIGIBLE — SAFE EXPLORATION CONDITIONS" if eligible else "NOT ELIGIBLE"


def policy_assurance_details(record):
    """Policy-layer assurance status kept separate from the Guideline colour and legal classification."""
    register_status = _value(record, "Register Status")
    lifecycle = {
        "BUV Provided / Assured": ("ASSURED — USE WITHIN APPROVED SCOPE", "institutional lifecycle decision is recorded; the approved scope and conditions still apply"),
        "Conditional": ("CONDITIONAL — USE ONLY WITHIN RECORDED CONDITIONS", "institutional conditional decision is recorded"),
        "Pilot": ("PILOT — TIME-BOUNDED USE ONLY", "pilot conditions, owner and expiry/review govern use; this is not wider production approval"),
        "Restricted": ("RESTRICTED — DO NOT USE FOR THIS SCOPE", "institutional restriction/rejection is recorded"),
        "Suspended": ("SUSPENDED — STOP UNTIL RE-AUTHORISED", "institutional suspension is recorded"),
        "Retired": ("RETIRED — NOT AN ACTIVE BUV SERVICE", "service/use is retired from the active register"),
    }
    if register_status in lifecycle:
        status, reason = lifecycle[register_status]
        return {"status": status, "reasons": [reason], "unknowns": []}

    existing = _value(record, "Existing Assurance Scope")
    facts = {
        "data classification": _value(record, "Data Classification"),
        "personal data": _personal_kind(record),
        "decision impact": _value(record, "Decision Impact"),
        "system integration": _value(record, "System Integration"),
        "autonomous actions": _value(record, "Autonomous Actions"),
        "procurement": _value(record, "Procurement Type"),
        "high-impact screening": _value(record, "Statutory High-Risk"),
        "research confidentiality": _value(record, "Research Confidentiality"),
        "assessment security": _value(record, "Secure Assessment Content"),
        "human participants / ethics": _value(record, "Human Participants / Ethics"),
        "NDA / contract": _value(record, "NDA / Contractual Restrictions"),
        "scale": _value(record, "Intended Scale"),
    }
    unknowns = [k for k, v in facts.items() if is_unknown(v)]
    if unknowns:
        return {"status": "INFORMATION REQUIRED", "reasons": ["complete the missing scope facts before assurance routing"], "unknowns": unknowns}

    # Existing assured scope is deliberately respected. Data already authorised for that exact
    # service/use does not by itself trigger reassessment. Only material/high-impact/changed-scope
    # facts below break out of routine use.
    if existing == "Existing BUV-assured service within approved scope":
        change_triggers = []
        if facts["decision impact"] == "Material / consequential decision": change_triggers.append("new consequential decision impact")
        if facts["high-impact screening"] and not facts["high-impact screening"].startswith("No known trigger"): change_triggers.append("possible statutory/high-impact trigger")
        if facts["research confidentiality"] == "Yes": change_triggers.append("research confidentiality route")
        if facts["assessment security"] == "Yes - live / secure assessment": change_triggers.append("live/secure assessment material")
        if facts["human participants / ethics"] in {"Yes", "Unknown"}: change_triggers.append("human-participant/ethics trigger")
        if facts["system integration"] in {"Write / action capability", "Privileged / broad access"}: change_triggers.append("write/action or privileged integration")
        if facts["autonomous actions"] in {"Limited with human confirmation", "Yes - consequential actions"}: change_triggers.append("new autonomous/semi-autonomous action")
        if change_triggers:
            return {"status": "FORMAL ASSESSMENT REQUIRED", "reasons": change_triggers, "unknowns": []}
        return {"status": "ROUTINE WITHIN EXISTING ASSURED SCOPE", "reasons": ["declared use remains inside the documented service, purpose, users, data class, integrations and conditions already assured by BUV"], "unknowns": []}

    reasons = []
    if facts["data classification"] in {"Confidential", "Restricted"}: reasons.append("Confidential/Restricted information")
    if facts["personal data"] in {"Pseudonymised / masked", "Basic / Ordinary identifiable", "Basic / Ordinary", "Sensitive / Special", "Large-scale / Systematic"}: reasons.append("personal data processing")
    if facts["decision impact"] == "Material / consequential decision": reasons.append("consequential impact on people or BUV")
    if facts["system integration"] != "None": reasons.append("connection to BUV systems/data")
    if facts["autonomous actions"] != "No": reasons.append("autonomous/semi-autonomous action")
    if not facts["high-impact screening"].startswith("No known trigger"): reasons.append("possible statutory/high-impact trigger")
    if facts["research confidentiality"] == "Yes": reasons.append("research confidentiality route")
    if facts["assessment security"] == "Yes - live / secure assessment": reasons.append("live/secure assessment material")
    if facts["human participants / ethics"] == "Yes": reasons.append("human-participant/ethics trigger")
    if facts["NDA / contract"] == "Yes": reasons.append("NDA/contractual restriction")
    if facts["procurement"] in {"Departmental pilot", "Paid institutional service"}: reasons.append("pilot/procurement")
    if facts["scale"] in {"Team / Department", "Pilot Cohort", "School / Function", "Institution-wide"}: reasons.append("deployment beyond individual exploration")
    if existing in {"Existing service — new/expanded use", "Conditional / Pilot scope"}: reasons.append("new/expanded or conditional scope")

    if reasons:
        return {"status": "FORMAL ASSESSMENT REQUIRED", "reasons": reasons, "unknowns": []}
    if safe_exploration_status(record).startswith("ELIGIBLE"):
        return {"status": "SAFE EXPLORATION ONLY — NOT PRODUCTION APPROVAL", "reasons": ["low-risk exploration conditions are met; this does not authorise controlled data or production deployment"], "unknowns": []}
    return {"status": "FORMAL ASSESSMENT REQUIRED", "reasons": ["new/unassessed use falls outside Safe Exploration conditions"], "unknowns": []}

def _holiday_dates():
    raw = HOLIDAY_CFG.get("dates") or HOLIDAY_CFG.get("holidays") or []
    out = set()
    for x in raw:
        try: out.add(date.fromisoformat(str(x)[:10]))
        except Exception: pass
    return out


def business_days_elapsed(start_date, end_date):
    if end_date < start_date: return 0
    holidays = _holiday_dates()
    days, cursor = 0, start_date
    while cursor < end_date:
        cursor += timedelta(days=1)
        if cursor.weekday() < 5 and cursor not in holidays:
            days += 1
    return days


def assessment_target_status(record):
    raw = _value(record, "Complete Request Date")
    if not raw: return "Complete request date not recorded"
    try: start = date.fromisoformat(raw[:10])
    except Exception: return "Complete request date is invalid"
    elapsed = business_days_elapsed(start, date.today())
    decision = _value(record, "Institutional Decision") or "Pending"
    qualifier = "configured working-day calendar" if _holiday_dates() else "weekends only; holidays not configured"
    if elapsed > ASSESSMENT_TARGET_DAYS and decision == "Pending":
        return f"{ASSESSMENT_TARGET_DAYS}-working-day target exceeded ({elapsed} working days; {qualifier}) — escalate; no automatic approval"
    if decision != "Pending":
        return f"Decision recorded after {elapsed} working days ({qualifier})"
    return f"Within {ASSESSMENT_TARGET_DAYS}-working-day target ({elapsed} working days; {qualifier})"


def required_reviews(record):
    req = {"privacy": False, "academic": False, "research_ethics": False, "procurement": False, "ict": False}
    # If this exact use is already inside a documented BUV-assured scope and no
    # material trigger breaks that scope, do not demand duplicate specialist sign-off.
    if policy_assurance_details(record)["status"] == "ROUTINE WITHIN EXISTING ASSURED SCOPE":
        return req
    personal = _personal_kind(record)
    domain = _value(record, "Purpose Domain")
    impact = _value(record, "Decision Impact")
    research = _value(record, "Research Confidentiality")
    high_risk = _value(record, "Statutory High-Risk")
    procurement = _value(record, "Procurement Type")
    nda = _value(record, "NDA / Contractual Restrictions")
    ethics = _value(record, "Human Participants / Ethics")
    secure = _value(record, "Secure Assessment Content")
    existing = _value(record, "Existing Assurance Scope")
    integration = _value(record, "System Integration")
    autonomy = _value(record, "Autonomous Actions")

    if personal not in {"", "None", "Fully anonymised under approved criteria"} or not high_risk.startswith("No known trigger") or nda in {"Yes", "Unknown"}:
        req["privacy"] = True
    if domain in {"Assessment", "Teaching & Learning", "Student Support"} and (impact != "No material effect" or secure != "No"):
        req["academic"] = True
    if secure == "Yes - live / secure assessment": req["academic"] = True
    if ethics in {"Yes", "Unknown"} or (domain == "Research" and research == "Yes"):
        req["research_ethics"] = True
    if procurement in {"Departmental pilot", "Paid institutional service"}:
        req["procurement"] = True
    if safe_exploration_status(record).startswith("ELIGIBLE"):
        req["ict"] = False
    elif existing != "Existing BUV-assured service within approved scope" or integration not in {"", "None"} or autonomy not in {"", "No"}:
        req["ict"] = True
    return req


def review_complete(value, required=False):
    status = normalise_text(value)
    if required:
        return status in {"Completed / No objection", "Completed / Conditions"}
    return status in {"Not required", "Completed / No objection", "Completed / Conditions"}


def criterion_applicability(record, criterion_id):
    """Return (Required|Recommended|Not in scope, rationale) using facts, not a numeric score."""
    cid = normalise_text(criterion_id)
    existing = _value(record, "Existing Assurance Scope")
    data_class = _value(record, "Data Classification")
    personal = _personal_kind(record)
    impact = _value(record, "Decision Impact")
    integration = _value(record, "System Integration")
    autonomy = _value(record, "Autonomous Actions")
    procurement = _value(record, "Procurement Type")
    scale = _value(record, "Intended Scale")
    domain = _value(record, "Purpose Domain")
    research = _value(record, "Research Confidentiality") == "Yes"
    ethics = _value(record, "Human Participants / Ethics")
    nda = _value(record, "NDA / Contractual Restrictions")
    secure = _value(record, "Secure Assessment Content")
    high_risk = _value(record, "Statutory High-Risk")
    policy_status = policy_assurance_details(record)["status"]
    formal = policy_status == "FORMAL ASSESSMENT REQUIRED"
    routine_existing = policy_status == "ROUTINE WITHIN EXISTING ASSURED SCOPE"
    material = impact in {"Human-reviewed decision support", "Material / consequential decision"}
    controlled = data_class in {"Internal", "Confidential", "Restricted"} or personal not in {"", "None", "Fully anonymised under approved criteria"}
    deployment = scale in {"Team / Department", "Pilot Cohort", "School / Function", "Institution-wide"} or procurement in {"Departmental pilot", "Paid institutional service"}

    if routine_existing:
        # A use-case confirmation inside an already assured scope should be light-touch.
        # Verify the scope/accountability boundary and reassessment controls rather than
        # re-running supplier/security/privacy due diligence already completed for that scope.
        if cid in {"C01","C03","C04","C17","C27","C28","C29"}:
            return "Required", "Confirm the use remains inside the documented assured scope and accountability boundary"
        if cid in {"C02","C14","C23","C30"}:
            return "Recommended", "Light-touch confirmation is useful for ongoing assured use"
        if cid == "C05" and personal not in {"", "None", "Fully anonymised under approved criteria"}:
            return "Recommended", "Confirm personal-data use remains within the existing approved privacy scope"
        if cid in {"C15","C16"} and material:
            return "Recommended", "Confirm meaningful human review remains effective within the approved workflow"
        return "Not in scope", "No new material trigger; rely on the existing BUV assurance record unless the scope changes"

    always = {"C01","C02","C03","C14","C17","C23","C27","C28"}
    if cid in always: return "Required", "Core scope, value, accountability and output assurance"
    if cid == "C04": return ("Required", "Information classification must match service scope") if (controlled or existing != "Existing BUV-assured service within approved scope") else ("Recommended", "Confirm data/service fit remains valid")
    if cid == "C05": return ("Required", "Personal data or privacy status requires evidence") if personal not in {"", "None", "Fully anonymised under approved criteria"} else ("Not in scope", "No personal data identified")
    if cid in {"C06","C07"}: return ("Required", "Data handling/transfer terms matter for controlled or research data") if (controlled or research or nda=="Yes") else ("Recommended", "Useful supplier data-handling assurance for low-risk use")
    if cid == "C08": return ("Required", "Account/tenant assurance required for controlled/deployed use") if (controlled or deployment or formal) else ("Recommended", "Confirm safe account model for exploration")
    if cid in {"C09","C10"}: return ("Required", "Access/logging controls needed for multi-user, integrated or deployed use") if (deployment or integration not in {"","None"} or formal) else ("Not in scope", "No material access/integration/deployment identified")
    if cid == "C11": return ("Required", "Integration permissions and revocation must be assessed") if integration not in {"","None"} else ("Not in scope", "No BUV system integration")
    if cid == "C12": return ("Required", "Autonomous action requires containment and human-control evidence") if autonomy not in {"","No"} else ("Not in scope", "No autonomous action")
    if cid == "C13": return ("Required", "Security and incident assurance required for formal/deployed service") if (formal or deployment or integration not in {"","None"}) else ("Recommended", "Proportionate supplier/incident check")
    if cid in {"C15","C16"}: return ("Required", "People-impact decision support requires fairness/explainability evidence") if material or not high_risk.startswith("No known trigger") else ("Not in scope", "No material people-impact identified")
    if cid == "C18": return ("Required", "Factual screening indicates possible high-impact/statutory trigger") if (not high_risk.startswith("No known trigger") or impact=="Material / consequential decision") else ("Recommended", "Document why no high-impact trigger is known")
    if cid in {"C19","C20","C21","C22"}: return ("Required", "Supplier/commercial evidence required for procurement, pilot or formal deployment") if (deployment or formal or research) else ("Recommended", "Light-touch supplier/IP/exit check for exploration")
    if cid == "C24": return ("Required", "Assessment/academic-integrity trigger") if (domain=="Assessment" or secure not in {"","No"} or (domain in {"Teaching & Learning","Student Support"} and material)) else ("Not in scope", "No assessment-security or material academic decision trigger")
    if cid == "C25": return ("Required", "Research confidentiality/IP/NDA trigger") if (research or nda=="Yes") else ("Not in scope", "No confidential research/IP/NDA trigger")
    if cid == "C26": return ("Required", "Human-participant/research-ethics trigger") if ethics in {"Yes","Unknown"} else ("Not in scope", "No human-participant/ethics trigger")
    if cid == "C29": return ("Required", "Review and material-change triggers needed for deployed/conditional use") if (deployment or formal or existing in {"Conditional / Pilot scope","Existing service — new/expanded use"}) else ("Recommended", "Lightweight reassessment triggers still useful")
    if cid == "C30": return ("Required", "Monitoring/incident/decommissioning controls needed for deployed use") if (deployment or formal or integration not in {"","None"}) else ("Recommended", "Basic incident/exit awareness for low-risk use")
    return "Recommended", "Proportionate evidence recommended"


def operational_lane_details(record):
    path = compute_pathway_details(record)
    pol = policy_assurance_details(record)
    req = required_reviews(record)
    if path["unknowns"]:
        return {"lane":"INFORMATION REQUIRED","may":"Complete the missing facts; no route is final yet.","stop":"Do not infer Green/Amber/Red or approval from incomplete information.","next":"Requester / use-case owner completes the scope.","evidence":"Only the missing scope facts are required now."}

    status = _value(record, "Register Status")
    if status == "BUV Provided / Assured":
        return {"lane":"ROUTINE ASSURED USE","may":"Use the service within its recorded BUV-approved purpose, users, data classes, integrations and conditions.","stop":"Do not silently expand purpose, data, users, integrations or autonomous capability.","next":"Use-case owner monitors suitability; reassess on material change.","evidence":"Rely on the recorded assurance scope and maintain change/review evidence."}
    if status == "Conditional":
        return {"lane":"CONDITIONAL USE","may":"Use only within the recorded conditions, owners and review/expiry date.","stop":"Do not exceed the stated conditions or treat the decision as unrestricted approval.","next":"Condition owners complete actions; decision owner reviews at the recorded date or on material change.","evidence":"Maintain evidence that each condition is implemented and effective."}
    if status == "Pilot":
        return {"lane":"CONTROLLED PILOT","may":"Run the time-bounded pilot only with the recorded users, data, integrations, monitoring and conditions.","stop":"Do not expand the pilot or treat it as wider production approval.","next":"Pilot owner monitors outcomes and returns for review/expiry decision.","evidence":"Pilot conditions, monitoring evidence, incidents/issues and exit/scale decision."}
    if status in {"Restricted","Suspended","Retired"}:
        return {"lane":"RESTRICTED / STOP","may":"Follow only the recorded restriction, suspension, retirement or authorised remediation action.","stop":"Do not use, resume or expand this scope unless an authorised reassessment changes the lifecycle decision.","next":"Decision owner / AI Governance route manages any reassessment or closure.","evidence":"Use the recorded decision, rationale, conditions and reassessment evidence."}

    if _value(record,"Research Confidentiality") == "Yes":
        needed = [label for label, flag in [("ICT/Cybersecurity",req["ict"]),("Privacy/Legal",req["privacy"]),("Academic/Professional",req["academic"]),("Research/Ethics",req["research_ethics"]),("Procurement",req["procurement"])] if flag]
        return {"lane":"RESEARCH CONFIDENTIALITY","may":"Use only an appropriately assured enterprise/API/research environment within the documented project scope.","stop":"Do not use unmanaged consumer accounts for confidential BUV research; do not treat pseudonymisation as anonymisation.","next":"Research owner/PI plus " + (", ".join(needed) if needed else "triggered specialist owner(s)"),"evidence":"Research confidentiality, contractual/IP and any triggered privacy/ethics/technical evidence."}
    if pol["status"] == "ROUTINE WITHIN EXISTING ASSURED SCOPE":
        return {"lane":"ROUTINE ASSURED USE","may":"Proceed within the already approved service, purpose, users, data class and recorded conditions.","stop":"Do not silently expand purpose, data, users, integrations or autonomous capability.","next":"Use-case owner; reassess on material change.","evidence":"Confirm the exact use remains inside the documented assured scope."}
    if safe_exploration_status(record).startswith("ELIGIBLE"):
        return {"lane":"SAFE EXPLORATION","may":"Explore now with public/synthetic/approved non-sensitive data only, without BUV system integration or production deployment.","stop":"Do not use confidential/restricted data, personal data that is not approved anonymised data, or connect the tool to BUV systems.","next":"Named owner may explore; request assessment before broader or controlled use.","evidence":"Record the bounded purpose, public/non-sensitive data and no-integration condition."}
    needed = [label for label, flag in [("ICT/Cybersecurity",req["ict"]),("Privacy/Legal",req["privacy"]),("Academic/Professional",req["academic"]),("Research/Ethics",req["research_ethics"]),("Procurement",req["procurement"])] if flag]
    return {"lane":"FORMAL ASSESSMENT","may":"Prepare evidence and complete the triggered specialist reviews. A controlled pilot may be considered only by the authorised owner with explicit conditions.","stop":"Do not treat the colour, score or elapsed time as approval; do not deploy or use controlled data until required reviews/decision are complete.","next":"Triggered owner(s): " + (", ".join(needed) if needed else "AI Governance / delegated decision owner"),"evidence":"Complete Required criteria; Recommended criteria are advisory unless a reviewer escalates them."}

def metrics_for(evaluation_id, record, responses, criteria=None):
    if criteria is None:
        _, _, criteria, _ = load_records()
    rows = [r for r in responses if normalise_text(r.get("Evaluation ID")) == evaluation_id]
    row_by_id = {normalise_text(r.get("Criterion ID")): r for r in rows}
    required_ids, recommended_ids, not_scope_ids = [], [], []
    for c in criteria:
        cid = normalise_text(c.get("Criterion ID"))
        app, rationale = criterion_applicability(record, cid)
        if app == "Required": required_ids.append(cid)
        elif app == "Recommended": recommended_ids.append(cid)
        else: not_scope_ids.append(cid)
    required_rows = [row_by_id.get(cid, {}) for cid in required_ids]
    req_assessed = [r for r in required_rows if normalise_text(r.get("Rating")) not in {"", "Not assessed", "N/A"}]
    required_completion = round(100 * len(req_assessed) / len(required_ids)) if required_ids else 100
    rec_rows = [row_by_id.get(cid, {}) for cid in recommended_ids]
    rec_assessed = [r for r in rec_rows if normalise_text(r.get("Rating")) not in {"", "Not assessed", "N/A"}]
    recommended_completion = round(100 * len(rec_assessed) / len(recommended_ids)) if recommended_ids else 100

    scored = [r for r in rows if normalise_text(r.get("Rating")) in {"Low","Medium","High"}]
    scores = [RATING_SCORE.get(normalise_text(r.get("Rating"))) for r in scored]
    scores = [x for x in scores if x is not None]
    avg = sum(scores)/len(scores) if scores else None
    high_count = sum(1 for r in scored if normalise_text(r.get("Rating"))=="High")
    medium_count = sum(1 for r in scored if normalise_text(r.get("Rating"))=="Medium")
    critical_high = sum(1 for r in scored if normalise_text(r.get("Critical Trigger"))=="Yes" and normalise_text(r.get("Rating"))=="High" and normalise_text(r.get("Review Status")) not in {"Ready","Closed"})
    open_actions = sum(1 for r in rows if normalise_text(r.get("Review Status")) in {"Open","Evidence needed","Mitigation required"})
    risk_index = "High" if critical_high or high_count >= 3 else ("Medium" if high_count or medium_count >= 3 else ("Low" if scored else "Not assessed"))

    req = required_reviews(record)
    pending_reviews=[]
    if req["privacy"] and not review_complete(record.get("Privacy / Legal Review"), True): pending_reviews.append("Privacy / Legal")
    if req["academic"] and not review_complete(record.get("Academic / Professional Review"), True): pending_reviews.append("Academic / Professional")
    if req["research_ethics"] and not review_complete(record.get("Research / Ethics Review"), True): pending_reviews.append("Research / Ethics")
    if req["procurement"] and not review_complete(record.get("Procurement Review"), True): pending_reviews.append("Procurement")
    if req["ict"] and _value(record,"Technical Finding") in {"","Not assessed","Not required — existing assured scope"}: pending_reviews.append("ICT technical assurance")

    decision = _value(record,"Institutional Decision") or "Pending"
    if critical_high: readiness="Critical issues unresolved"
    elif pending_reviews: readiness="Specialist review needed"
    elif required_completion < 100: readiness="Required evidence incomplete"
    elif decision == "Pending": readiness="Ready for decision"
    else: readiness="Decision recorded"

    path_detail=compute_pathway_details(record); policy_detail=policy_assurance_details(record); lane=operational_lane_details(record)
    workflow=workflow_state(record, required_completion, pending_reviews, critical_high)
    return {
        "completion": required_completion,
        "required_completion": required_completion,
        "recommended_completion": recommended_completion,
        "required_count": len(required_ids), "recommended_count": len(recommended_ids), "not_in_scope_count": len(not_scope_ids),
        "required_ids": required_ids, "recommended_ids": recommended_ids, "not_in_scope_ids": not_scope_ids,
        "risk_index": risk_index, "average_score": round(avg,2) if avg is not None else None,
        "high_count": high_count, "medium_count": medium_count, "critical_high": critical_high, "open_actions": open_actions,
        "pending_reviews": pending_reviews, "readiness": readiness,
        "next_action": lane["next"], "pathway": path_detail["pathway"], "pathway_reasons": path_detail["reasons"], "pathway_provisional": path_detail["provisional"],
        "policy_assurance": policy_detail["status"], "policy_reasons": policy_detail["reasons"], "safe_exploration": safe_exploration_status(record),
        "assessment_target": assessment_target_status(record), "operational_lane": lane["lane"], "what_may_happen_now": lane["may"], "stop_do_not": lane["stop"],
        "next_owner_action": lane["next"], "evidence_requirement": lane["evidence"],
        "reassessment_triggers": "Reassess on material change to purpose, model/capability, vendor terms, data, integrations, autonomous functions, users/scale or legal/contractual context.",
        "workflow_step": workflow["step"], "workflow_label": workflow["label"], "workflow_missing": workflow["missing"], "workflow_complete": workflow["complete"],
        "workflow_percent": 100 if workflow["complete"] else round(((workflow["step"]-1)/10)*100), "required_reviews": req,
    }


def workflow_state(record, completion, pending_reviews, critical_high=0):
    required_by_step = {
        1:["Tool / Service","Purpose Domain","Primary Use Case"],
        2:["Requesting Unit","Sponsor / AI System Owner","User Group","Intended Scale","Existing Assurance Scope"],
        3:["Data Classification","Personal Data","Research Confidentiality","Secure Assessment Content","Human Participants / Ethics","NDA / Contractual Restrictions","Decision Impact","Statutory High-Risk"],
        4:["System Integration","Autonomous Actions","Procurement Type"],
    }
    for step, fields in required_by_step.items():
        missing=[f for f in fields if is_unknown(record.get(f))]
        if missing: return {"step":step,"label":BLUEPRINT_STEPS[step-1]["title"],"missing":missing,"complete":False}
    stage=_value(record,"Assurance Stage")
    if not _value(record,"Evaluation ID"): return {"step":4,"label":BLUEPRINT_STEPS[3]["title"],"missing":[],"complete":False}
    if stage not in {"Guideline route reviewed","Evidence complete","Specialist review","Ready for decision","Decision recorded"}: return {"step":5,"label":BLUEPRINT_STEPS[4]["title"],"missing":[],"complete":False}
    if completion < 100: return {"step":6,"label":BLUEPRINT_STEPS[5]["title"],"missing":[],"complete":False}
    if pending_reviews: return {"step":7,"label":BLUEPRINT_STEPS[6]["title"],"missing":list(pending_reviews),"complete":False}
    decision=_value(record,"Institutional Decision") or "Pending"
    if decision=="Pending": return {"step":8,"label":BLUEPRINT_STEPS[7]["title"],"missing":[],"complete":False}
    expected={"Approve":"BUV Provided / Assured","Conditional":"Conditional","Pilot":"Pilot","Reject":"Restricted","Suspend":"Suspended","Retire":"Retired"}
    if decision in expected and _value(record,"Register Status")!=expected[decision]: return {"step":9,"label":BLUEPRINT_STEPS[8]["title"],"missing":[],"complete":False}
    if decision in {"Conditional","Pilot"} and not _value(record,"Review Date"): return {"step":10,"label":BLUEPRINT_STEPS[9]["title"],"missing":["Review Date"],"complete":False}
    return {"step":10,"label":"Completed — review / reassessment","missing":[],"complete":decision!="Pending"}

def next_evaluation_id(register):
    year = datetime.now().year
    max_n = 0
    prefix = f"AI-{year}-"
    for r in register:
        eid = normalise_text(r.get("Evaluation ID"))
        if eid.startswith(prefix):
            try:
                max_n = max(max_n, int(eid.split("-")[-1]))
            except ValueError:
                pass
    return f"{prefix}{max_n + 1:04d}"


def upsert_record(records, key_header, key_value, record):
    key_value = normalise_text(key_value)
    for idx, existing in enumerate(records):
        if normalise_text(existing.get(key_header)) == key_value:
            merged = dict(existing)
            merged.update(record)
            records[idx] = merged
            return
    records.append(dict(record))


def criterion_map(records):
    return {normalise_text(r.get("Criterion ID")): r for r in records if normalise_text(r.get("Criterion ID"))}


def save_evaluation(payload):
    record = dict(payload.get("record") or {})
    incoming = payload.get("responses") or []
    with LOCK:
        backup_workbook()
        db=XlsxDatabase(DATA_FILE)
        register=db.records(REGISTER_SHEET); responses=db.records(RESPONSES_SHEET); criteria=db.records(CRITERIA_SHEET)
        eid=_value(record,"Evaluation ID") or next_evaluation_id(register)
        record["Evaluation ID"]=eid
        path=compute_pathway_details(record); policy=policy_assurance_details(record); lane=operational_lane_details(record); req=required_reviews(record)
        record.update({
            "Pathway":path["pathway"], "Pathway Evidence Summary":"; ".join(path["reasons"]), "Policy Assurance Trigger":policy["status"],
            "Safe Exploration Eligibility":safe_exploration_status(record), "Assessment Target Status":assessment_target_status(record),
            "Operational Lane":lane["lane"], "What May Happen Now":lane["may"], "Stop / Do Not":lane["stop"], "Next Owner / Action":lane["next"],
            "Required Reviews":", ".join([x for x,flag in [("ICT/Cybersecurity",req["ict"]),("Privacy/Legal",req["privacy"]),("Academic/Professional",req["academic"]),("Research/Ethics",req["research_ethics"]),("Procurement",req["procurement"])] if flag]) or "None triggered by current facts",
            "Evidence Requirement":lane["evidence"],
            "Reassessment / Change Triggers":"Purpose, model/capability, vendor terms, data, integrations, autonomous functions, users/scale or legal/contractual context materially changes.",
        })
        if not _value(record,"Register Status"): record["Register Status"]="Unassessed"
        if not _value(record,"Institutional Decision"): record["Institutional Decision"]="Pending"
        if not _value(record,"Assurance Stage"): record["Assurance Stage"]="Evidence gathering"
        record["Last Updated"]=datetime.now().isoformat(timespec="seconds")
        upsert_record(register,"Evaluation ID",eid,record)

        existing_rows={normalise_text(r.get("Criterion ID")):r for r in responses if normalise_text(r.get("Evaluation ID"))==eid}
        incoming_by={normalise_text(r.get("Criterion ID")):r for r in incoming}
        responses=[r for r in responses if normalise_text(r.get("Evaluation ID"))!=eid]
        new_rows=[]
        for crit in sorted(criteria,key=lambda c:int(c.get("Sort Order") or 999)):
            cid=normalise_text(crit.get("Criterion ID")); old=existing_rows.get(cid,{}); inc=incoming_by.get(cid,{})
            applicability, rationale=criterion_applicability(record,cid)
            rating=normalise_text(inc.get("Rating") if "Rating" in inc else old.get("Rating")) or "Not assessed"
            if applicability=="Not in scope": rating="N/A"
            elif rating=="N/A" and normalise_text(old.get("Applicability"))=="Not in scope": rating="Not assessed"
            new_rows.append({
                "Evaluation ID":eid,"Criterion ID":cid,"Domain":crit.get("Domain"),"Criterion":crit.get("Criterion"),"Primary Owner":crit.get("Primary Owner"),"Critical Trigger":crit.get("Critical Trigger"),
                "Rating":rating,"Score":RATING_SCORE.get(rating),"Evidence / Source":inc.get("Evidence / Source",old.get("Evidence / Source","")),"Finding / Notes":inc.get("Finding / Notes",old.get("Finding / Notes","")),
                "Mitigation / Condition":inc.get("Mitigation / Condition",old.get("Mitigation / Condition","")),"Action Owner":inc.get("Action Owner",old.get("Action Owner","")),"Due Date":inc.get("Due Date",old.get("Due Date","")),
                "Review Status":inc.get("Review Status",old.get("Review Status","Open")),"Updated At":datetime.now().isoformat(timespec="seconds"),"Applicability":applicability,"Applicability Rationale":rationale,
            })
        responses.extend(new_rows)
        db.set_records(REGISTER_SHEET,register); db.set_records(RESPONSES_SHEET,responses); db.save(DATA_FILE)
    register,responses,criteria,_=load_records(); saved=next((r for r in register if _value(r,"Evaluation ID")==eid),record)
    metrics=metrics_for(eid,saved,responses,criteria)
    audit_event("evaluation_saved", evaluation_id=eid, pathway=metrics["pathway"], lane=metrics["operational_lane"], stage=saved.get("Assurance Stage"))
    return {"ok":True,"evaluation_id":eid,"record":saved,"metrics":metrics}


def save_decision(payload):
    eid=normalise_text(payload.get("evaluation_id"))
    if not eid: raise ValueError("evaluation_id is required")
    decision=payload.get("decision") or {}
    with LOCK:
        backup_workbook(); db=XlsxDatabase(DATA_FILE)
        register=db.records(REGISTER_SHEET); decisions=db.records(DECISION_SHEET); responses=db.records(RESPONSES_SHEET); criteria=db.records(CRITERIA_SHEET)
        current=next((r for r in register if _value(r,"Evaluation ID")==eid),None)
        if current is None: raise ValueError(f"Unknown Evaluation ID: {eid}")
        merged={**current,**decision}; decision_type=_value(merged,"Institutional Decision") or "Pending"; register_status=_value(merged,"Register Status") or "Unassessed"
        if decision_type!="Pending":
            if not _value(merged,"Decision Owner"): raise ValueError("Record the delegated Decision Owner before saving a final decision.")
            if not _value(merged,"Rationale"): raise ValueError("Record the decision rationale/evidence considered before saving a final decision.")
        expected={"Approve":"BUV Provided / Assured","Conditional":"Conditional","Pilot":"Pilot","Reject":"Restricted","Suspend":"Suspended","Retire":"Retired"}
        if decision_type in expected and register_status!=expected[decision_type]: raise ValueError(f"For decision '{decision_type}', set Register Status to '{expected[decision_type]}'.")
        if decision_type in {"Conditional","Pilot"}:
            if not _value(merged,"Conditions Summary"): raise ValueError("Conditional/Pilot decisions require a clear Conditions Summary.")
            if not _value(merged,"Review Date"): raise ValueError("Conditional/Pilot decisions require a Review Date.")

        req=required_reviews(merged); outstanding=[]
        if decision_type in {"Approve","Conditional","Pilot"}:
            if req["ict"] and _value(merged,"Technical Finding") in {"","Not assessed","Not required — existing assured scope"}: outstanding.append("ICT technical assurance")
            if req["privacy"] and not review_complete(merged.get("Privacy / Legal Review"),True): outstanding.append("Privacy / Legal")
            if req["academic"] and not review_complete(merged.get("Academic / Professional Review"),True): outstanding.append("Academic / Professional")
            if req["research_ethics"] and not review_complete(merged.get("Research / Ethics Review"),True): outstanding.append("Research / Ethics")
            if req["procurement"] and not review_complete(merged.get("Procurement Review"),True): outstanding.append("Procurement")
            if outstanding: raise ValueError("Complete the required specialist review(s) before recording this decision: "+", ".join(outstanding))
            response_map={_value(r,"Criterion ID"):r for r in responses if _value(r,"Evaluation ID")==eid}
            incomplete=[]
            for c in criteria:
                cid=_value(c,"Criterion ID"); app,_=criterion_applicability(merged,cid); rr=response_map.get(cid,{})
                if app=="Required" and _value(rr,"Rating") not in {"Low","Medium","High"}: incomplete.append(cid)
            if incomplete: raise ValueError(f"Complete the Required evidence criteria before recording this decision: {len(incomplete)} outstanding ({', '.join(incomplete[:8])}{'…' if len(incomplete)>8 else ''}).")
            unresolved=[r for r in responses if _value(r,"Evaluation ID")==eid and _value(r,"Critical Trigger")=="Yes" and _value(r,"Rating")=="High" and _value(r,"Review Status") not in {"Ready","Closed"}]
            if decision_type=="Approve" and unresolved: raise ValueError("Approve cannot be recorded while Critical High findings remain unresolved. Mitigate/close them or choose an appropriate conditional/pilot/non-approval outcome.")
        if _value(merged,"Technical Finding")=="Technical Risk Identified" and decision_type in {"Approve","Conditional","Pilot"} and not _value(merged,"Residual Risk Owner"):
            raise ValueError("A delegated Residual Risk Owner is required where Technical Risk Identified is accepted or conditionally managed.")

        updates={k:merged.get(k,"") for k in ["Technical Finding","Privacy / Legal Review","Academic / Professional Review","Research / Ethics Review","Procurement Review","Institutional Decision","Register Status","Conditions Summary","Residual Risk Owner","Review Date"]}
        updates["Assurance Stage"]="Decision recorded" if decision_type!="Pending" else "Ready for decision"; updates["Last Updated"]=datetime.now().isoformat(timespec="seconds")
        # Recalculate post-decision lane/policy fields using lifecycle status.
        post={**current,**updates}
        lane=operational_lane_details(post); policy=policy_assurance_details(post)
        updates.update({"Policy Assurance Trigger":policy["status"],"Operational Lane":lane["lane"],"What May Happen Now":lane["may"],"Stop / Do Not":lane["stop"],"Next Owner / Action":lane["next"],"Evidence Requirement":lane["evidence"]})
        upsert_record(register,"Evaluation ID",eid,updates)
        decision_id=f"DEC-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(2).upper()}"
        decisions.append({"Decision ID":decision_id,"Evaluation ID":eid,"Decision Date":decision.get("Decision Date") or date.today().isoformat(),"Decision Type":decision_type,"Register Status":register_status,"Decision Owner":decision.get("Decision Owner") or "","Support Functions":decision.get("Support Functions") or "","Conditions / Required Actions":updates.get("Conditions Summary","") or "","Residual Risk Accepted By":updates.get("Residual Risk Owner","") or "","Review Date":updates.get("Review Date","") or "","Rationale":decision.get("Rationale") or "","Recorded By":decision.get("Recorded By") or "","Timestamp":datetime.now().isoformat(timespec="seconds")})
        db.set_records(REGISTER_SHEET,register); db.set_records(DECISION_SHEET,decisions); db.save(DATA_FILE)
    audit_event("decision_recorded", evaluation_id=eid, decision_id=decision_id, decision=decision_type, register_status=register_status, owner=decision.get("Decision Owner"), recorded_by=decision.get("Recorded By"))
    return {"ok":True,"evaluation_id":eid,"decision_id":decision_id}


def preview_payload(record):
    record=dict(record or {})
    _,_,criteria,_=load_records()
    fake=[]
    for c in criteria:
        app,rat=criterion_applicability(record,c.get("Criterion ID"))
        fake.append({"Evaluation ID":"PREVIEW","Criterion ID":c.get("Criterion ID"),"Critical Trigger":c.get("Critical Trigger"),"Rating":"N/A" if app=="Not in scope" else "Not assessed","Review Status":"Open","Applicability":app,"Applicability Rationale":rat})
    metrics=metrics_for("PREVIEW",record,fake,criteria)
    applicability=[]
    for c in criteria:
        app,rat=criterion_applicability(record,c.get("Criterion ID")); applicability.append({"criterion_id":c.get("Criterion ID"),"applicability":app,"rationale":rat})
    return {"metrics":metrics,"applicability":applicability,"governance_sources":GOVERNANCE_SOURCES}


def dashboard_payload():
    register,responses,criteria,decisions=load_records(); enriched=[]; today=date.today()
    for rec in register:
        eid=_value(rec,"Evaluation ID")
        if not eid: continue
        metrics=metrics_for(eid,rec,responses,criteria); item=dict(rec); item["metrics"]=metrics
        rd=_value(rec,"Review Date"); due=False; overdue=False
        if rd:
            try:
                d=date.fromisoformat(rd[:10]); due=today<=d<=today+timedelta(days=REVIEW_DUE_DAYS); overdue=d<today
            except Exception: pass
        item["review_due_30"]=due; item["review_overdue"]=overdue; enriched.append(item)
    def count(field,value): return sum(1 for r in enriched if _value(r,field)==value)
    status_counts={}; path_counts={}; lane_counts={}
    for r in enriched:
        status=_value(r,"Register Status") or "Unassessed"; path=r["metrics"]["pathway"] or "Unspecified"; lane=r["metrics"]["operational_lane"] or "Information Required"
        status_counts[status]=status_counts.get(status,0)+1; path_counts[path]=path_counts.get(path,0)+1; lane_counts[lane]=lane_counts.get(lane,0)+1
    attention=[r for r in enriched if r["metrics"]["critical_high"]>0 or r["review_overdue"] or r["metrics"]["pending_reviews"] or str(r["metrics"].get("assessment_target","")).startswith(f"{ASSESSMENT_TARGET_DAYS}-working-day target exceeded")]
    attention.sort(key=lambda r:(r["metrics"]["critical_high"],r["review_overdue"],len(r["metrics"]["pending_reviews"])),reverse=True)
    queue=[r for r in enriched if _value(r,"Institutional Decision") in {"","Pending"}]; queue.sort(key=lambda r:_value(r,"Last Updated"),reverse=True)
    modified=datetime.fromtimestamp(DATA_FILE.stat().st_mtime).isoformat(timespec="seconds")
    return {"generated_at":datetime.now().isoformat(timespec="seconds"),"backend_modified":modified,"version":APP_VERSION,"release_label":RELEASE_LABEL,"governance_sources":GOVERNANCE_SOURCES,
        "kpis":{"evaluations":len(enriched),"pending_decision":len(queue),"assured":count("Register Status","BUV Provided / Assured"),"conditional":count("Register Status","Conditional"),"pilot":count("Register Status","Pilot"),"restricted":count("Register Status","Restricted"),"critical_unresolved":sum(1 for r in enriched if r["metrics"]["critical_high"]>0),"review_due":sum(1 for r in enriched if r["review_due_30"] or r["review_overdue"]),"needs_attention":len(attention),"formal_assessment":sum(1 for r in enriched if r["metrics"]["operational_lane"]=="FORMAL ASSESSMENT")},
        "status_counts":status_counts,"path_counts":path_counts,"lane_counts":lane_counts,"tools":enriched,"queue":queue[:12],"attention":attention[:12],"criteria_count":len(criteria),"decision_count":len(decisions)}

class Handler(SimpleHTTPRequestHandler):
    server_version = "BUVAI/2.0"
    def __init__(self,*args,**kwargs): super().__init__(*args,directory=str(ROOT),**kwargs)
    def log_message(self,fmt,*args):
        msg=fmt%args; SYSTEM_LOG.info("http %s %s", self.client_address[0], msg); sys.stdout.write("[BUV Dashboard] "+msg+"\n")
    def end_headers(self):
        self.send_header("X-Content-Type-Options","nosniff"); self.send_header("X-Frame-Options","DENY"); self.send_header("Referrer-Policy","no-referrer")
        self.send_header("Content-Security-Policy","default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; base-uri 'self'; frame-ancestors 'none'")
        self.send_header("Permissions-Policy","camera=(), microphone=(), geolocation=()")
        super().end_headers()
    def _host_ok(self):
        host=(self.headers.get("Host") or "").split(":")[0].strip("[]").lower(); return host in {"127.0.0.1","localhost",HOST.lower()}
    def _origin_ok(self):
        origin=self.headers.get("Origin");
        if not origin: return True
        try: return urlparse(origin).hostname in {"127.0.0.1","localhost",HOST}
        except Exception: return False
    def send_json(self,data,status=200):
        raw=json.dumps(data,ensure_ascii=False,default=serialise).encode("utf-8"); self.send_response(status); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(raw))); self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(raw)
    def read_json(self):
        try: length=int(self.headers.get("Content-Length","0") or 0)
        except Exception: raise ValueError("Invalid request length")
        if length>MAX_REQUEST_BYTES: raise ValueError(f"Request is too large. Maximum is {MAX_REQUEST_BYTES} bytes.")
        raw=self.rfile.read(length) if length else b"{}"; return json.loads(raw.decode("utf-8"))
    def _error(self,exc,status=500):
        eid=secrets.token_hex(4).upper(); SYSTEM_LOG.exception("request_error id=%s path=%s",eid,self.path); return self.send_json({"ok":False,"error":"The request could not be completed.","error_id":eid,"support":"See logs/system.log and diagnostics. Do not send assessment content unless authorised."},status)
    def do_GET(self):
        if not self._host_ok(): return self.send_json({"ok":False,"error":"Invalid host"},400)
        parsed=urlparse(self.path)
        try:
            if parsed.path=="/api/health": return self.send_json({"ok":True,"version":APP_VERSION,"release_label":RELEASE_LABEL,"workflow":"10-step Guided Evaluation Blueprint","data_file":DATA_FILE.name,"exists":DATA_FILE.exists(),"governance_sources":GOVERNANCE_SOURCES.get("status")})
            if parsed.path=="/api/blueprint": return self.send_json({"version":APP_VERSION,"steps":BLUEPRINT_STEPS,"scenarios":SCENARIO_STARTERS,"governance_sources":GOVERNANCE_SOURCES,"traffic":[{"name":"GREEN","meaning":"Routine low-risk governance route; not an approval label."},{"name":"AMBER","meaning":"Proportionate local control; assured scope and meaningful human review matter."},{"name":"RED","meaning":"Prior formal review for higher-impact, sensitive, integrated or autonomous use."},{"name":"RESEARCH CONFIDENTIALITY","meaning":"Protected route for unpublished, proprietary, patent or NDA-bound research."}]})
            if parsed.path=="/api/dashboard": return self.send_json(dashboard_payload())
            if parsed.path=="/api/criteria":
                _,_,criteria,_=load_records(); criteria.sort(key=lambda r:int(r.get("Sort Order") or 999)); return self.send_json({"criteria":criteria})
            if parsed.path=="/api/evaluation":
                eid=_value(parse_qs(parsed.query).get("id",[""])[0]); register,responses,criteria,decisions=load_records(); record=next((r for r in register if _value(r,"Evaluation ID")==eid),None)
                if not record: return self.send_json({"ok":False,"error":"Evaluation not found"},404)
                rows=[r for r in responses if _value(r,"Evaluation ID")==eid]; history=[r for r in decisions if _value(r,"Evaluation ID")==eid]
                return self.send_json({"record":record,"responses":rows,"metrics":metrics_for(eid,record,responses,criteria),"decision_history":history,"criteria":criteria})
            if parsed.path=="/api/backend/download":
                data=DATA_FILE.read_bytes(); self.send_response(200); self.send_header("Content-Type","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"); self.send_header("Content-Disposition",'attachment; filename="BUV_AI_Evaluation_Backend.xlsx"'); self.send_header("Content-Length",str(len(data))); self.end_headers(); self.wfile.write(data); audit_event("backend_downloaded"); return
            if parsed.path=="/api/diagnostics":
                mem=io.BytesIO();
                with zipfile.ZipFile(mem,"w",zipfile.ZIP_DEFLATED) as z:
                    for rel in ["version.json","config/settings.json","config/governance_sources.json","config/holidays.json","logs/system.log","logs/audit.jsonl"]:
                        fp=ROOT/rel
                        if fp.exists(): z.write(fp,arcname=rel)
                    z.writestr("diagnostics/README.txt","Diagnostics intentionally exclude the Excel backend and assessment/evidence content.\n")
                data=mem.getvalue(); self.send_response(200); self.send_header("Content-Type","application/zip"); self.send_header("Content-Disposition",'attachment; filename="BUV_AI_Dashboard_Diagnostics.zip"'); self.send_header("Content-Length",str(len(data))); self.end_headers(); self.wfile.write(data); audit_event("diagnostics_downloaded"); return
            return super().do_GET()
        except Exception as exc: return self._error(exc,500)
    def do_POST(self):
        if not self._host_ok() or not self._origin_ok(): return self.send_json({"ok":False,"error":"Request origin is not allowed"},403)
        try:
            payload=self.read_json(); parsed=urlparse(self.path)
            if parsed.path=="/api/preview": return self.send_json(preview_payload(payload.get("record") or payload))
            if parsed.path=="/api/save_evaluation": return self.send_json(save_evaluation(payload))
            if parsed.path=="/api/save_decision": return self.send_json(save_decision(payload))
            return self.send_json({"ok":False,"error":"Unknown API endpoint"},404)
        except ValueError as exc:
            SYSTEM_LOG.warning("validation_error path=%s error=%s",self.path,str(exc)); return self.send_json({"ok":False,"error":str(exc)},400)
        except PermissionError:
            return self.send_json({"ok":False,"error":"The Excel backend is locked by another application. Save and close the workbook, then try again."},423)
        except Exception as exc: return self._error(exc,500)

def self_test():
    required=[REGISTER_SHEET,RESPONSES_SHEET,CRITERIA_SHEET,DECISION_SHEET,"Lookups"]
    ok,detail=validate_xlsx(DATA_FILE,required)
    if not ok: raise SystemExit("Backend check failed: "+detail)
    register,responses,criteria,decisions=load_records()
    if len(criteria)!=30: raise SystemExit(f"Backend check failed: expected 30 assessment criteria, found {len(criteria)}")
    headers=XlsxDatabase(DATA_FILE)._headers_for(REGISTER_SHEET)
    for h in ["Operational Lane","What May Happen Now","Stop / Do Not","Next Owner / Action","Required Reviews","Evidence Requirement","Reassessment / Change Triggers"]:
        if h not in headers: raise SystemExit(f"Backend check failed: missing AI_Register column '{h}'")
    rheaders=XlsxDatabase(DATA_FILE)._headers_for(RESPONSES_SHEET)
    for h in ["Applicability","Applicability Rationale"]:
        if h not in rheaders: raise SystemExit(f"Backend check failed: missing Assessment_Responses column '{h}'")
    print(f"SELF-TEST OK — Dashboard v{APP_VERSION}")
    print(f"Release: {RELEASE_LABEL}")
    print(f"Backend: {DATA_FILE.name}")
    print(f"Criteria: {len(criteria)}")
    print(f"Evaluations: {len(register)}")
    print("Decision engine: operational lane + governance route + specialist routing")
    print("Logging: privacy-minimised system/audit logs enabled")
    print("No third-party Python packages are required.")


def main():
    if not DATA_FILE.exists(): raise SystemExit(f"Backend Excel file is missing: {DATA_FILE}")
    try:
        server=ThreadingHTTPServer((HOST,PORT),Handler)
    except OSError as exc:
        raise SystemExit(f"Could not start on http://{HOST}:{PORT}/. The dashboard may already be running. Details: {exc}")
    url=f"http://{HOST}:{PORT}/"; SYSTEM_LOG.info("server_start version=%s url=%s",APP_VERSION,url); audit_event("server_started")
    print("="*72); print(f"BUV AI Evaluation Dashboard v{APP_VERSION}"); print(RELEASE_LABEL); print(f"Open: {url}"); print(f"Excel backend: {DATA_FILE}"); print(f"Logs: {LOG_DIR}"); print("Press Ctrl+C to stop."); print("="*72)
    try: threading.Timer(1.0,lambda:webbrowser.open(url)).start()
    except Exception: pass
    try: server.serve_forever()
    except KeyboardInterrupt: print("\\nDashboard stopped.")
    finally:
        server.server_close(); audit_event("server_stopped"); SYSTEM_LOG.info("server_stop")


if __name__=="__main__":
    if "--self-test" in sys.argv: self_test()
    else: main()
