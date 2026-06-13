"""
Google Sheets integration for the Application Tracker.

Reads credentials from `credentials.json` in the project root.
Sheet ID is read from GOOGLE_SHEET_ID env var.

If Google Sheets is not configured, all functions raise SheetsNotConfigured
and the caller falls back to the local-file tracker.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

SHEET_HEADERS = [
    "id", "date_applied", "company", "job_title", "job_url", "location",
    "contract_type", "inside_ir35", "day_rate_or_salary", "source",
    "recruiter_name", "recruiter_contact", "cv_variant", "cv_latex", "status",
    "stage_detail", "next_action", "next_action_date", "jd_text", "notes",
    "outcome", "offer_amount", "visa_sponsorship_needed", "last_updated",
]

_CREDS_PATH = Path(__file__).parent.parent / "credentials.json"


class SheetsNotConfigured(Exception):
    pass


def _client():
    import gspread
    from google.oauth2.service_account import Credentials

    sheet_id = os.environ.get("GOOGLE_SHEET_ID", "")
    if not sheet_id:
        raise SheetsNotConfigured("GOOGLE_SHEET_ID not set in .env")
    if not _CREDS_PATH.exists():
        raise SheetsNotConfigured(f"credentials.json not found at {_CREDS_PATH}")

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(str(_CREDS_PATH), scopes=scopes)
    gc = gspread.authorize(creds)
    return gc, sheet_id


def _worksheet(tab: str = "Applications"):
    gc, sheet_id = _client()
    sh = gc.open_by_key(sheet_id)
    return sh.worksheet(tab)


def _row_to_dict(headers: list[str], row: list) -> dict:
    d = {}
    for i, h in enumerate(headers):
        d[h] = row[i] if i < len(row) else ""
    return d


def get_all_applications() -> list[dict]:
    ws = _worksheet("Applications")
    records = ws.get_all_values()
    if len(records) < 2:
        return []
    headers = records[0]
    return [_row_to_dict(headers, row) for row in records[1:] if any(row)]


def add_application(data: dict) -> str:
    ws = _worksheet("Applications")
    headers = ws.row_values(1) or SHEET_HEADERS
    row_id = data.get("id") or str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    data["id"] = row_id
    data.setdefault("date_applied", now[:10])
    data["last_updated"] = now
    row = [str(data.get(h, "")) for h in headers]
    ws.append_row(row, value_input_option="USER_ENTERED")
    return row_id


def update_application(row_id: str, data: dict) -> bool:
    ws = _worksheet("Applications")
    records = ws.get_all_values()
    if not records:
        return False
    headers = records[0]
    id_col = headers.index("id") + 1 if "id" in headers else 1
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for i, row in enumerate(records[1:], start=2):
        if row[id_col - 1] == row_id:
            data["last_updated"] = now
            for col_idx, h in enumerate(headers, start=1):
                if h in data:
                    ws.update_cell(i, col_idx, str(data[h]))
            return True
    return False


def archive_application(row_id: str) -> bool:
    ws_main = _worksheet("Applications")
    ws_arch = _worksheet("Archive")
    records = ws_main.get_all_values()
    if not records:
        return False
    headers = records[0]
    id_col_idx = headers.index("id") if "id" in headers else 0
    for i, row in enumerate(records[1:], start=2):
        if row[id_col_idx] == row_id:
            ws_arch.append_row(row, value_input_option="USER_ENTERED")
            ws_main.delete_rows(i)
            return True
    return False


def get_stats() -> dict:
    apps = get_all_applications()
    total = len(apps)
    active_statuses = {"applied", "cv_sent", "interview_1", "interview_2", "final_round"}
    active = [a for a in apps if a.get("status", "").lower() in active_statuses]
    interviews = [a for a in apps if a.get("status", "").lower() in {"interview_1", "interview_2", "final_round"}]
    offers = [a for a in apps if a.get("outcome", "").lower() == "offer"]

    response_rate = round(len(interviews) / len(active) * 100) if active else 0

    # Average days from applied to first interview response
    days_list = []
    for a in interviews:
        applied = a.get("date_applied", "")
        updated = a.get("last_updated", "")
        if applied and updated:
            try:
                d1 = datetime.fromisoformat(applied[:10])
                d2 = datetime.fromisoformat(updated[:10])
                days_list.append((d2 - d1).days)
            except ValueError:
                pass
    avg_days = round(sum(days_list) / len(days_list)) if days_list else 0

    return {
        "total": total,
        "active": len(active),
        "interviews": len(interviews),
        "offers": len(offers),
        "response_rate": response_rate,
        "avg_days_to_response": avg_days,
    }
