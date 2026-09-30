# Sheets Create + Format + Share — verified working pattern

Complete flow used to build a job-application tracker spreadsheet
(verified working 2026-09-03 against Sheets v4 / Drive v3).

## Prerequisites

```bash
# Check auth first
~/.hermes/gws-venv/bin/python \
  ~/.hermes/skills/productivity/google-workspace/scripts/setup.py --check
# -> AUTHENTICATED

# Check scopes (sharing needs full drive scope, not drive.readonly)
python3 -c "import json; print(json.load(open('$HOME/.hermes/google_token.json'))['scopes'])"
```

## Full script

```python
#!/usr/bin/env python3
import json, sys
sys.path.insert(0, "$HOME/.hermes/skills/productivity/google-workspace/scripts")
from google_api import get_credentials
from googleapiclient.discovery import build

EDITOR_EMAIL = "collaborator@example.com"
TITLE = "Tracker Name"
TAB = "Applications"           # tab title
HEADERS = ["Col1", "Col2", "..."]  # N columns
WIDTHS = [150, 200, ...]       # pixelSize per column, same length as HEADERS

creds = get_credentials()
sheets = build("sheets", "v4", credentials=creds)
drive = build("drive", "v3", credentials=creds)

# 1. Create
spreadsheet = sheets.spreadsheets().create(body={
    "properties": {"title": TITLE},
    "sheets": [{"properties": {
        "title": TAB,
        "gridProperties": {"columnCount": len(HEADERS), "rowCount": 200},
    }}],
}).execute()
sid = spreadsheet["spreadsheetId"]

# 2. Headers
sheets.spreadsheets().values().update(
    spreadsheetId=sid, range=f"{TAB}!A1:{chr(64+len(HEADERS))}1",
    valueInputOption="RAW", body={"values": [HEADERS]},
).execute()

# 3. Resolve the real sheetId of the tab (NOT 0 for created sheets!)
meta = sheets.spreadsheets().get(
    spreadsheetId=sid, fields="sheets(properties(sheetId,title))").execute()
sh = next(s["properties"]["sheetId"] for s in meta["sheets"]
          if s["properties"]["title"] == TAB)

# 4. Format — HEADER ROW ONLY (frozen, bold, navy). No banding, no data-row
#    backgrounds. Data rows: wrap + vertical middle only (invisible).
navy = {"red": 0.10, "green": 0.18, "blue": 0.35}
white = {"red": 1, "green": 1, "blue": 1}
requests = [
    {"updateSheetProperties": {"properties": {
        "sheetId": sh, "gridProperties": {"frozenRowCount": 1}},
     "fields": "gridProperties.frozenRowCount"}},
    {"repeatCell": {
        "range": {"sheetId": sh, "startRowIndex": 0, "endRowIndex": 1,
                  "startColumnIndex": 0, "endColumnIndex": len(HEADERS)},
        "cell": {"userEnteredFormat": {
            "textFormat": {"bold": True, "fontSize": 11,
                           "foregroundColor": white},
            "backgroundColor": navy,
            "horizontalAlignment": "LEFT",
            "verticalAlignment": "MIDDLE",          # NOT verticalAlign
            "padding": {"top": 6, "bottom": 6, "left": 8, "right": 8}}},
        "fields": "userEnteredFormat(textFormat,horizontalAlignment,"
                  "verticalAlignment,backgroundColor,padding)"}},
    # column widths
    *[{"updateDimensionProperties": {
        "range": {"sheetId": sh, "dimension": "COLUMNS",
                  "startIndex": i, "endIndex": i + 1},
        "properties": {"pixelSize": w}, "fields": "pixelSize"}}
      for i, w in enumerate(WIDTHS)],
    # data rows: wrap + center only, plain white, non-bold
    {"repeatCell": {
        "range": {"sheetId": sh, "startRowIndex": 1, "endRowIndex": 200,
                  "startColumnIndex": 0, "endColumnIndex": len(HEADERS)},
        "cell": {"userEnteredFormat": {
            "wrapStrategy": "WRAP",
            "verticalAlignment": "MIDDLE",
            "padding": {"top": 4, "bottom": 4, "left": 8, "right": 8}}},
        "fields": "userEnteredFormat(wrapStrategy,verticalAlignment,padding)"}},
]
sheets.spreadsheets().batchUpdate(spreadsheetId=sid,
                                  body={"requests": requests}).execute()

# 5. Share as editor (no notification email)
drive.permissions().create(
    fileId=sid,
    body={"type": "user", "role": "writer", "emailAddress": EDITOR_EMAIL},
    sendNotificationEmail=False,
    fields="id,emailAddress,role",
).execute()

# 6. Verify
perms = drive.permissions().list(
    fileId=sid, fields="permissions(id,emailAddress,role)").execute()
row = sheets.spreadsheets().values().get(
    spreadsheetId=sid, range=f"{TAB}!A1:K1").execute()
print(sid, perms["permissions"], row["values"])
```

## Cleanup pattern (if a previous pass over-formatted)

If banded ranges or explicit data-row backgrounds/bold were applied and need
removing:

```python
# find bandedRangeId
meta = sheets.spreadsheets().get(spreadsheetId=sid,
    fields="sheets(properties(sheetId,title),bandedRanges)").execute()
requests = [
    {"deleteBanding": {"bandedRangeId": BR_ID}},
    # plain white background on data rows
    {"repeatCell": {
        "range": {"sheetId": sh, "startRowIndex": 1, "endRowIndex": 201,
                  "startColumnIndex": 0, "endColumnIndex": N},
        "cell": {"userEnteredFormat":
                 {"backgroundColor": {"red": 1, "green": 1, "blue": 1}}},
        "fields": "userEnteredFormat.backgroundColor"}},
    # un-bold data rows (bold can persist in effectiveFormat even after the
    # background clear, so set it explicitly false)
    {"repeatCell": {
        "range": {"sheetId": sh, "startRowIndex": 1, "endRowIndex": 201,
                  "startColumnIndex": 0, "endColumnIndex": N},
        "cell": {"userEnteredFormat": {"textFormat": {"bold": False}}},
        "fields": "userEnteredFormat.textFormat.bold"}},
]
```

## Verify formatting state

```python
fields = 'sheets(data(rowData(values(effectiveFormat(backgroundColor,textFormat(bold))))))'
fmt = sheets.spreadsheets().get(spreadsheetId=sid, ranges=[f"{TAB}!A1:K2"],
    includeGridData=True, fields=fields).execute()
# row 1: bg ~(0.1, 0.18, 0.35), bold True
# row 2+: bg (1, 1, 1), bold False
```

Note the FieldMask: one closing paren per opened group. And
`bandedRanges` is under `sheets(...)`, not top-level.