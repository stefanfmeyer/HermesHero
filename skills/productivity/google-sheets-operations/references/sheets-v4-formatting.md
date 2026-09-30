# Sheets v4 Formatting — Working Snippets, Verification, Error Transcripts

Real patterns from building and debugging a formatted shared spreadsheet
(Sarah Keevan job tracker, Sep 2026). All snippets verified against live API.

## Setup

```python
import sys
sys.path.insert(0, "$HOME/.hermes/skills/productivity/google-workspace/scripts")
from google_api import get_credentials
from googleapiclient.discovery import build
creds = get_credentials()
sheets = build("sheets", "v4", credentials=creds)
drive = build("drive", "v3", credentials=creds)
```

## batchUpdate request snippets

### Frozen header + styled header row (navy bg, white bold text)

```python
requests = [
    {"updateSheetProperties": {"properties": {
        "sheetId": SHEET_ID, "gridProperties": {"frozenRowCount": 1}},
        "fields": "gridProperties.frozenRowCount"}},
    {"repeatCell": {
        "range": {"sheetId": SHEET_ID, "startRowIndex": 0, "endRowIndex": 1,
                  "startColumnIndex": 0, "endColumnIndex": NCOLS},
        "cell": {"userEnteredFormat": {
            "textFormat": {"bold": True, "fontSize": 11,
                           "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
            "backgroundColor": {"red": 0.10, "green": 0.18, "blue": 0.35},
            "horizontalAlignment": "LEFT",
            "verticalAlignment": "MIDDLE",       # NOT verticalAlign
            "padding": {"top": 6, "bottom": 6, "left": 8, "right": 8}}},
        "fields": "userEnteredFormat(textFormat,horizontalAlignment,verticalAlignment,backgroundColor,padding)"}},
]
```

### Banding (alternating colours) — add

```python
{"addBanding": {"bandedRange": {
    "range": {"sheetId": SHEET_ID, "startRowIndex": 1, "endRowIndex": 200,
              "startColumnIndex": 0, "endColumnIndex": NCOLS},
    "rowProperties": {                  # NOT rowBanding
        "headerColor": {"red": 1, "green": 1, "blue": 1},
        "firstBandColor": {"red": 1, "green": 1, "blue": 1},
        "secondBandColor": {"red": 0.94, "green": 0.95, "blue": 0.98}}}}}
```

### Banding — remove

Find the id first, then delete:
```python
meta = sheets.spreadsheets().get(spreadsheetId=SID,
    fields="sheets(properties(sheetId,title),bandedRanges)").execute()
for br in meta["sheets"][0].get("bandedRanges", []):
    requests.append({"deleteBanding": {"bandedRangeId": br["bandedRangeId"]}})
```

### Plain data rows (white bg, black non-bold text) — the safe default

```python
{"repeatCell": {
    "range": {"sheetId": SHEET_ID, "startRowIndex": 1, "endRowIndex": 201,
              "startColumnIndex": 0, "endColumnIndex": NCOLS},
    "cell": {"userEnteredFormat": {
        "backgroundColor": {"red": 1, "green": 1, "blue": 1},
        "textFormat": {"bold": False,
                       "foregroundColor": {"red": 0, "green": 0, "blue": 0}},
        "wrapStrategy": "WRAP",
        "verticalAlignment": "MIDDLE",
        "padding": {"top": 4, "bottom": 4, "left": 8, "right": 8}}},
    "fields": "userEnteredFormat(backgroundColor,textFormat,wrapStrategy,verticalAlignment,padding)"}}
```

### Borders

```python
b = {"style": "SOLID", "width": 1, "color": {"red": 0.8, "green": 0.8, "blue": 0.85}}
{"updateBorders": {"range": {...gridrange...},
    "top": b, "bottom": b, "left": b, "right": b,
    "innerHorizontal": b, "innerVertical": b}}
```

### Column widths

```python
{"updateDimensionProperties": {
    "range": {"sheetId": SHEET_ID, "dimension": "COLUMNS",
              "startIndex": i, "endIndex": i + 1},
    "properties": {"pixelSize": w}, "fields": "pixelSize"}}
```

## Field-mask verification queries

Read effective formatting of a range (note balanced parens — every nested
opening group needs a closing paren):

```python
fields = "sheets(data(rowData(values(effectiveFormat(backgroundColor,textFormat(bold,foregroundColor))))))"
fmt = sheets.spreadsheets().get(spreadsheetId=SID, ranges=["Tab!A1:K2"],
    includeGridData=True, fields=fields).execute()
```

Check hidden rows / filters / merges (why "user can't see the data"):
```python
meta = sheets.spreadsheets().get(spreadsheetId=SID).execute()  # no fields mask
sh = meta["sheets"][0]
sh.get("filterViews"); sh.get("basicFilter"); sh.get("merges")
# rowMetadata[i]["hiddenInUI"] via includeGridData + rowMetadata
```

## Error transcript (real 400s and their fixes)

1. `Unknown name "verticalAlign" at ...repeat_cell.cell.user_entered_format`
   → field is `verticalAlignment` (full word, camelCase).

2. `Unknown name "rowBanding" at ...add_banding.banded_range`
   → field is `rowProperties` inside `bandedRange`.

3. `No sheet with id: 0` on updateSheetProperties
   → custom-named tabs get random sheetIds (e.g. 1420244526). Fetch the real
   id from `sheets(properties(sheetId,title))` before any sheetId-scoped
   request; never assume 0.

4. `Cannot find matching fields for path 'bandedRanges'` (top-level mask)
   → read banding via `sheets(properties(sheetId,title),bandedRanges)`.

5. `Invalid FieldMask ... Cannot find matching ')' for all '('`
   → count nested groups in the fields mask; every opening paren needs a close.

## Data-loss trap (real incident)

After a formatting cleanup batch, a data row's values came back as the same
string repeated across all 11 cells ("Resultful" x11) — the row was mangled
during the banding/format operations. Fix: always re-read values with
`sheets get` on every data range after ANY formatting batchUpdate, and restore
from known data if mangled. Verify formatting AND values, every time.

## Share + verify permissions

```python
perm = drive.permissions().create(fileId=SID,
    body={"type": "user", "role": "writer", "emailAddress": EMAIL},
    sendNotificationEmail=False, fields="id,emailAddress,role").execute()
perms = drive.permissions().list(fileId=SID,
    fields="permissions(id,emailAddress,role)").execute()
```

## User preferences recorded during this build (the user)

- Header row only may be coloured/bold; data rows plain white bg, black text,
  non-bold. Banding rejected as "messy".
- After any visible-formatting change, confirm what the user sees in the UI —
  effective (inherited) formats can render white-on-white even when values
  are present and the API reports the data as correct.