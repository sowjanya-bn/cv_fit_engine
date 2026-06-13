# Application Tracker — Google Sheets Setup

The Application Tracker stores your pipeline in Google Sheets so you can access it on any device.

## One-time setup

### 1. Google Cloud project

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a project (or reuse an existing one)
3. Enable **Google Sheets API** and **Google Drive API**

### 2. Service account credentials

1. IAM & Admin → Service Accounts → Create Service Account
2. Grant it no special roles (Editor on the sheet is enough)
3. Create a JSON key → download as `credentials.json`
4. Place `credentials.json` in the project root (it's already in `.gitignore`)

### 3. Google Sheet

1. Create a new Google Sheet at [sheets.google.com](https://sheets.google.com)
2. Copy the Sheet ID from the URL:
   `https://docs.google.com/spreadsheets/d/**SHEET_ID**/edit`
3. Share the sheet with the service account email (find it in `credentials.json` under `client_email`) — give it **Editor** access

### 4. Add to `.env`

```
GOOGLE_SHEET_ID=your_sheet_id_here
```

### 5. Run setup script

```bash
python scripts/setup_sheet.py
```

This creates the `Applications` and `Archive` tabs with correct headers, freezes the header row, and verifies the connection.

---

## Without Google Sheets

If `GOOGLE_SHEET_ID` is not set or `credentials.json` is missing, the tracker falls back to local files at `~/.cvfit/applications/`. All features still work.

---

## Data columns

| Column | Description |
|---|---|
| id | UUID auto-generated |
| date_applied | ISO date, auto-filled |
| company | Free text |
| job_title | Free text |
| job_url | Link to posting |
| location | e.g. Manchester, Remote |
| contract_type | Permanent / Contract / FTC |
| inside_ir35 | inside / outside / undetermined |
| day_rate_or_salary | e.g. £540/day, £65k |
| source | LinkedIn / Recruiter / Direct / Reed / Adzuna |
| recruiter_name | Optional |
| recruiter_contact | Optional |
| cv_variant | .tex filename used |
| status | Pipeline stage (see below) |
| stage_detail | Free text e.g. "1st stage booked 14 Jun" |
| next_action | Free text e.g. "Await feedback by Friday" |
| next_action_date | Date for chasing / sorting |
| jd_text | Full JD — used for interview prep |
| notes | Running log — append don't replace |
| outcome | Pending / Offer / Rejected / Withdrawn / Ghost |
| offer_amount | If offer received |
| visa_sponsorship_needed | flag |
| last_updated | Auto-set on any edit |

## Status lifecycle

```
applied → cv_sent → interview_1 → interview_2 → final_round → offer
                                                             → rejected
                       → rejected (at any stage)
                       → ghost (no response)
          → withdrawn (you pulled out)
```

Terminal outcomes (rejected / ghost / withdrawn) move the row to the `Archive` sheet when you click Archive in the detail panel.
