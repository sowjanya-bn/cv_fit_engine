#!/usr/bin/env python3
"""
One-time setup script for the Application Tracker Google Sheet.

Run from the project root:
    python scripts/setup_sheet.py

Requires:
  - credentials.json in the project root
  - GOOGLE_SHEET_ID set in .env
"""

import os
import sys
from pathlib import Path

# Load .env from project root
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

try:
    from dotenv import load_dotenv
    load_dotenv(project_root / ".env")
except ImportError:
    pass

HEADERS = [
    "id", "date_applied", "company", "job_title", "job_url", "location",
    "contract_type", "inside_ir35", "day_rate_or_salary", "source",
    "recruiter_name", "recruiter_contact", "cv_variant", "status",
    "stage_detail", "next_action", "next_action_date", "jd_text", "notes",
    "outcome", "offer_amount", "visa_sponsorship_needed", "last_updated",
]

STATUS_VALUES = ["applied", "cv_sent", "interview_1", "interview_2", "final_round", "offer", "rejected", "ghost", "withdrawn"]
CONTRACT_VALUES = ["Permanent", "Contract", "FTC"]
OUTCOME_VALUES = ["Pending", "Offer", "Rejected", "Withdrawn", "Ghost"]


def main():
    sheet_id = os.environ.get("GOOGLE_SHEET_ID", "")
    if not sheet_id:
        print("ERROR: GOOGLE_SHEET_ID not set in .env")
        sys.exit(1)

    creds_path = project_root / "credentials.json"
    if not creds_path.exists():
        print(f"ERROR: credentials.json not found at {creds_path}")
        sys.exit(1)

    try:
        import gspread
        from google.oauth2.service_account import Credentials
        from gspread_formatting import (
            format_cell_range, CellFormat, TextFormat, Color,
            set_frozen, DataValidationRule, BooleanCondition,
            set_data_validation_for_cell_range,
        )
    except ImportError:
        # gspread_formatting is optional
        gspread_formatting = None

    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        print("ERROR: gspread not installed. Run: pip install gspread google-auth")
        sys.exit(1)

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(str(creds_path), scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(sheet_id)

    for tab_name in ["Applications", "Archive"]:
        try:
            ws = sh.worksheet(tab_name)
            print(f"Tab '{tab_name}' already exists — skipping creation.")
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet(title=tab_name, rows=1000, cols=len(HEADERS))
            print(f"Created tab '{tab_name}'.")

        # Write headers if row 1 is empty
        existing = ws.row_values(1)
        if not existing or existing[0] != "id":
            ws.update([HEADERS], "A1")
            print(f"  Wrote headers to '{tab_name}'.")

        # Freeze header row
        sh.batch_update({
            "requests": [{
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": ws.id,
                        "gridProperties": {"frozenRowCount": 1},
                    },
                    "fields": "gridProperties.frozenRowCount",
                }
            }]
        })
        print(f"  Froze header row in '{tab_name}'.")

    # Add a test row to Applications, then delete it
    ws_main = sh.worksheet("Applications")
    import uuid, datetime
    test_row = [""] * len(HEADERS)
    test_row[HEADERS.index("id")] = f"_test_{uuid.uuid4().hex[:8]}"
    test_row[HEADERS.index("company")] = "__setup_test__"
    test_row[HEADERS.index("date_applied")] = datetime.date.today().isoformat()
    test_row[HEADERS.index("last_updated")] = datetime.datetime.utcnow().isoformat()
    ws_main.append_row(test_row, value_input_option="USER_ENTERED")
    all_vals = ws_main.get_all_values()
    # Find and delete test row
    for i, row in enumerate(all_vals[1:], start=2):
        if len(row) > 0 and row[0].startswith("_test_"):
            ws_main.delete_rows(i)
            print("  Test row written and deleted — connection verified.")
            break

    print("\nSetup complete. Your Google Sheet is ready for the Application Tracker.")
    print(f"Sheet ID: {sheet_id}")


if __name__ == "__main__":
    main()
