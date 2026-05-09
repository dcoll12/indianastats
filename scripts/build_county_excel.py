"""
Build an interactive Google Sheets workbook: County → Candidates lookup.

Import the output .xlsx into Google Sheets (File → Import, or just open it
from Drive — Google Sheets handles .xlsx natively).

Sheets produced:
  County Lookup  – dropdown (92 counties) + QUERY formula shows all candidates
  By District    – flat reference table with auto-filter
  All Data       – hidden source table (powering QUERY formula)
  Apps Script    – Google Apps Script code + setup instructions

Google Sheets QUERY formula drives live updates — no macros needed.
The Apps Script tab provides optional enhancements (toast notifications,
row highlight on change) for users who want extra interactivity.
"""

import json
import os
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import FormulaRule

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
BLUE_DARK  = "0C2340"
BLUE_MID   = "1E4488"
GOLD       = "C8962E"
GOLD_LIGHT = "F5DFA0"
WHITE      = "FFFFFF"
GREY_LIGHT = "F2F4F7"
GREY_MED   = "D0D5DD"
RED_LIGHT  = "FFE4E4"
BLUE_LIGHT = "E4EEFF"
GREEN_LIGHT= "E4F5E4"

def thin(top=True, bottom=True, left=True, right=True):
    sides = {n: Side(style="thin", color=GREY_MED) if f else Side(style=None)
             for n, f in [("top",top),("bottom",bottom),("left",left),("right",right)]}
    return Border(**sides)

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

with open(os.path.join(base, "data", "candidates_2026.json")) as f:
    cands = json.load(f)
with open(os.path.join(base, "data", "district_data.json")) as f:
    dm = json.load(f)

TYPE_ORDER = {"House": 1, "Senate": 2, "Congressional": 3}

rows = []
for county in sorted(dm["all_counties"]):
    for hd in sorted(dm["county_to_hds"].get(county, [])):
        for c in cands.get("hd", {}).get(str(hd), []):
            rows.append((county, 1, "House",         hd, f"HD-{hd}", c["name"], c["party"]))
    for sd in sorted(dm["county_to_sds"].get(county, [])):
        for c in cands.get("sd", {}).get(str(sd), []):
            rows.append((county, 2, "Senate",        sd, f"SD-{sd}", c["name"], c["party"]))
    for cd in sorted(dm["county_to_cds"].get(county, [])):
        for c in cands.get("cd", {}).get(str(cd), []):
            rows.append((county, 3, "Congressional", cd, f"CD-{cd}", c["name"], c["party"]))

all_counties = sorted(dm["all_counties"])
last_data_row = len(rows) + 1   # +1 for header

# ---------------------------------------------------------------------------
wb = Workbook()
wb.remove(wb.active)

# ============================================================
# Sheet: All Data  (hidden — QUERY source)
# Columns: A=County  B=SortOrder  C=Type  D=Num  E=District  F=Candidate  G=Party
# ============================================================
ws_data = wb.create_sheet("All Data")
ws_data.sheet_state = "hidden"

DATA_HEADERS = ["County", "SortOrder", "Type", "Num", "District", "Candidate", "Party"]
ws_data.append(DATA_HEADERS)
for r in rows:
    ws_data.append(list(r))

for col, _ in enumerate(DATA_HEADERS, 1):
    cell = ws_data.cell(1, col)
    cell.font      = Font(bold=True, color=WHITE, size=10)
    cell.fill      = PatternFill("solid", fgColor=BLUE_DARK)
    cell.alignment = Alignment(horizontal="center")

ws_data.column_dimensions["A"].width = 18
ws_data.column_dimensions["B"].width = 10
ws_data.column_dimensions["C"].width = 16
ws_data.column_dimensions["D"].width = 6
ws_data.column_dimensions["E"].width = 10
ws_data.column_dimensions["F"].width = 35
ws_data.column_dimensions["G"].width = 8

# ============================================================
# Sheet: County Lookup  (tab 1 — main interactive sheet)
# ============================================================
ws_lu = wb.create_sheet("County Lookup", 0)

# ---- Banner ----
ws_lu.merge_cells("A1:H1")
banner = ws_lu["A1"]
banner.value     = "Indiana 2026 Primary Candidates — County Lookup"
banner.font      = Font(bold=True, size=16, color=WHITE)
banner.fill      = PatternFill("solid", fgColor=BLUE_DARK)
banner.alignment = Alignment(horizontal="center", vertical="center")
ws_lu.row_dimensions[1].height = 38

ws_lu.merge_cells("A2:H2")
sub = ws_lu["A2"]
sub.value     = "Select a county from the dropdown to view all 2026 primary candidates in that county's House, Senate, and Congressional districts."
sub.font      = Font(size=10, color=BLUE_DARK, italic=True)
sub.fill      = PatternFill("solid", fgColor=GOLD_LIGHT)
sub.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
ws_lu.row_dimensions[2].height = 28

ws_lu.row_dimensions[3].height = 8  # spacer

# ---- County selector ----
ws_lu.merge_cells("B4:C4")
lbl = ws_lu["B4"]
lbl.value     = "Select County:"
lbl.font      = Font(bold=True, size=12, color=BLUE_DARK)
lbl.alignment = Alignment(horizontal="right", vertical="center")
ws_lu.row_dimensions[4].height = 28

sel = ws_lu["D4"]
sel.value     = all_counties[0]
sel.font      = Font(bold=True, size=12, color=BLUE_DARK)
sel.fill      = PatternFill("solid", fgColor=GOLD_LIGHT)
sel.alignment = Alignment(horizontal="center", vertical="center")
sel.border    = thin()

# Data validation dropdown — embed all county names directly so it works
# both in Google Sheets and Excel without a named range.
dv = DataValidation(
    type="list",
    formula1='"' + ",".join(all_counties) + '"',
    allow_blank=False,
    showDropDown=False,
    showErrorMessage=True,
    error="Please select a valid Indiana county.",
    errorTitle="Invalid County",
)
dv.sqref = "D4"
ws_lu.add_data_validation(dv)

# ---- Candidate count ----
ws_lu.row_dimensions[5].height = 8  # spacer

ws_lu.merge_cells("B6:C6")
cnt_lbl = ws_lu["B6"]
cnt_lbl.value     = "Candidates found:"
cnt_lbl.font      = Font(size=10, color=BLUE_DARK)
cnt_lbl.alignment = Alignment(horizontal="right", vertical="center")

# COUNTA on the spill area col E (Candidate column), rows 9 onward
ws_lu["D6"].value     = '=IFERROR(COUNTA(E9:E2000),0)'
ws_lu["D6"].font      = Font(bold=True, size=10, color=BLUE_DARK)
ws_lu["D6"].alignment = Alignment(horizontal="center")
ws_lu.row_dimensions[6].height = 20

ws_lu.row_dimensions[7].height = 8  # spacer

# ---- Results header row ----
result_cols    = ["B",  "C",      "D",      "E",               "F"]
result_headers = ["District", "Type", "Dist #", "Candidate Name", "Party"]

for col_letter, hdr in zip(result_cols, result_headers):
    cell = ws_lu[f"{col_letter}8"]
    cell.value     = hdr
    cell.font      = Font(bold=True, size=11, color=WHITE)
    cell.fill      = PatternFill("solid", fgColor=BLUE_MID)
    cell.alignment = Alignment(horizontal="center", vertical="center")
    cell.border    = thin()
ws_lu.row_dimensions[8].height = 24

# ---- QUERY formula (Google Sheets native) ----
# All Data columns by name: County SortOrder Type Num District Candidate Party
# We SELECT District(E), Type(C), Num(D), Candidate(F), Party(G)
# ORDER BY SortOrder ASC, Num ASC
# headers=1 tells QUERY that row 1 of the source is a header row.
query_formula = (
    "=IFERROR("
    "QUERY('All Data'!A:G,"
    "\"SELECT E, C, D, F, G "
    "WHERE A = '\"&D4&\"' "
    "ORDER BY B ASC, D ASC\","
    "1),"
    "{\"No candidates found for this county.\",\"\",\"\",\"\",\"\"})"
)
ws_lu["B9"].value = query_formula

# ---- Conditional formatting: Party column (F) ----
ws_lu.conditional_formatting.add(
    "F9:F2000",
    FormulaRule(formula=['$F9="D"'],
                fill=PatternFill("solid", fgColor=RED_LIGHT),
                font=Font(color="8B0000", bold=True)),
)
ws_lu.conditional_formatting.add(
    "F9:F2000",
    FormulaRule(formula=['$F9="R"'],
                fill=PatternFill("solid", fgColor=BLUE_LIGHT),
                font=Font(color="00008B", bold=True)),
)
ws_lu.conditional_formatting.add(
    "F9:F2000",
    FormulaRule(formula=['AND($F9<>"D",$F9<>"R",$F9<>"")'],
                fill=PatternFill("solid", fgColor=GREEN_LIGHT),
                font=Font(color="005500", bold=True)),
)

# ---- Column widths ----
ws_lu.column_dimensions["A"].width = 3
ws_lu.column_dimensions["B"].width = 12   # District label
ws_lu.column_dimensions["C"].width = 16   # Type
ws_lu.column_dimensions["D"].width = 9    # Dist #
ws_lu.column_dimensions["E"].width = 40   # Candidate Name
ws_lu.column_dimensions["F"].width = 8    # Party
ws_lu.column_dimensions["G"].width = 3

ws_lu.freeze_panes = "B9"
ws_lu.sheet_properties.tabColor = GOLD

# ============================================================
# Sheet: By District  (sorted reference table with auto-filter)
# ============================================================
ws_bd = wb.create_sheet("By District")

ws_bd.merge_cells("A1:F1")
ws_bd["A1"].value     = "Indiana 2026 Primary Candidates — All Districts"
ws_bd["A1"].font      = Font(bold=True, size=14, color=WHITE)
ws_bd["A1"].fill      = PatternFill("solid", fgColor=BLUE_DARK)
ws_bd["A1"].alignment = Alignment(horizontal="center", vertical="center")
ws_bd.row_dimensions[1].height = 30

bd_hdrs = ["County", "District", "Type", "Dist #", "Candidate Name", "Party"]
ws_bd.append(bd_hdrs)
for col, hdr in enumerate(bd_hdrs, 1):
    cell = ws_bd.cell(2, col)
    cell.font      = Font(bold=True, size=10, color=WHITE)
    cell.fill      = PatternFill("solid", fgColor=BLUE_MID)
    cell.alignment = Alignment(horizontal="center")
    cell.border    = thin()
ws_bd.row_dimensions[2].height = 20

sorted_rows = sorted(rows, key=lambda r: (r[1], r[3], r[0], r[5]))  # SortOrder, Num, County, Candidate
for idx, r in enumerate(sorted_rows, 3):
    county, _order, dtype, dnum, dlabel, cand, party = r
    vals = [county, dlabel, dtype, dnum, cand, party]
    bg = GREY_LIGHT if idx % 2 == 0 else WHITE
    for col, val in enumerate(vals, 1):
        cell = ws_bd.cell(idx, col)
        cell.value     = val
        cell.fill      = PatternFill("solid", fgColor=bg)
        cell.alignment = Alignment(vertical="center")
        cell.border    = thin()
    pcell = ws_bd.cell(idx, 6)
    if party == "D":
        pcell.fill = PatternFill("solid", fgColor=RED_LIGHT)
        pcell.font = Font(color="8B0000", bold=True, size=10)
    elif party == "R":
        pcell.fill = PatternFill("solid", fgColor=BLUE_LIGHT)
        pcell.font = Font(color="00008B", bold=True, size=10)
    else:
        pcell.fill = PatternFill("solid", fgColor=GREEN_LIGHT)
        pcell.font = Font(color="005500", bold=True, size=10)

ws_bd.column_dimensions["A"].width = 18
ws_bd.column_dimensions["B"].width = 10
ws_bd.column_dimensions["C"].width = 15
ws_bd.column_dimensions["D"].width = 8
ws_bd.column_dimensions["E"].width = 40
ws_bd.column_dimensions["F"].width = 8
ws_bd.freeze_panes = "A3"
ws_bd.auto_filter.ref = f"A2:F{len(sorted_rows)+2}"
ws_bd.sheet_properties.tabColor = BLUE_MID

# ============================================================
# Sheet: Apps Script  (setup instructions + full script source)
# ============================================================
ws_as = wb.create_sheet("Apps Script")

ws_as.merge_cells("A1:G1")
ws_as["A1"].value     = "Google Apps Script — Optional Enhancements"
ws_as["A1"].font      = Font(bold=True, size=13, color=WHITE)
ws_as["A1"].fill      = PatternFill("solid", fgColor=BLUE_DARK)
ws_as["A1"].alignment = Alignment(horizontal="center", vertical="center")
ws_as.row_dimensions[1].height = 28

instructions = [
    ("A3",  "WHY ADD APPS SCRIPT?"),
    ("A4",  "The QUERY formula handles lookups automatically — no script needed for basic use."),
    ("A5",  "The Apps Script below adds: a toast notification when you change county, a dynamic"),
    ("A6",  "page title update, and a manual Refresh button in the toolbar."),
    ("A8",  "HOW TO ADD THE SCRIPT:"),
    ("A9",  "1. In Google Sheets, go to Extensions → Apps Script."),
    ("A10", "2. Delete any placeholder code in the editor."),
    ("A11", "3. Copy ALL of the script from row 17 onward and paste it into the editor."),
    ("A12", "4. Click Save (Ctrl+S), then close the Apps Script tab."),
    ("A13", "5. Back in the sheet, reload the page — the onEdit trigger activates automatically."),
    ("A14", "6. (Optional) Go to Extensions → Apps Script → Triggers to verify onEdit is listed."),
    ("A16", "── APPS SCRIPT CODE BELOW ──"),
]

for addr, text in instructions:
    cell = ws_as[addr]
    cell.value     = text
    cell.alignment = Alignment(wrap_text=True)
    if addr in ("A3", "A8"):
        cell.font = Font(bold=True, size=11, color=BLUE_DARK)
    elif addr == "A16":
        cell.font = Font(bold=True, size=10, color=GOLD)
    else:
        cell.font = Font(size=10)

apps_script = r"""
// ============================================================
//  Paste this entire file into Extensions → Apps Script
//  (replaces any placeholder code already there)
// ============================================================

/**
 * Fires whenever any cell is edited.
 * When D4 on "County Lookup" changes, shows a brief toast.
 */
function onEdit(e) {
  const sheet = e.source.getActiveSheet();
  if (sheet.getName() !== 'County Lookup') return;
  if (e.range.getA1Notation() !== 'D4') return;

  const county = e.range.getValue();
  if (!county) return;

  // Brief toast notification bottom-right
  e.source.toast(
    'Showing candidates for ' + county,
    'County Lookup',
    3   // seconds to display
  );

  // Highlight the selector cell briefly then restore
  highlightSelector(sheet);
}

/**
 * Flash the county selector cell gold → white to signal the update.
 */
function highlightSelector(sheet) {
  const cell = sheet.getRange('D4');
  const original = cell.getBackground();
  cell.setBackground('#F5DFA0');   // gold flash
  SpreadsheetApp.flush();
  Utilities.sleep(300);
  cell.setBackground(original);
}

/**
 * Optional: call this from a custom menu or button to force-refresh
 * any cached formula results.
 */
function refreshLookup() {
  const ss    = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName('County Lookup');
  if (!sheet) return;

  // Toggle the county value to force QUERY to re-evaluate
  const cell   = sheet.getRange('D4');
  const county = cell.getValue();
  cell.clearContent();
  SpreadsheetApp.flush();
  cell.setValue(county);

  ss.toast('Refreshed: ' + county, 'County Lookup', 2);
}

/**
 * Adds a custom "IRS Tools" menu when the spreadsheet opens.
 */
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('IRS Tools')
    .addItem('Refresh County Lookup', 'refreshLookup')
    .addSeparator()
    .addItem('Go to County Lookup', 'goToLookup')
    .addItem('Go to By District', 'goToByDistrict')
    .addToUi();
}

function goToLookup() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  ss.setActiveSheet(ss.getSheetByName('County Lookup'));
  ss.getSheetByName('County Lookup').getRange('D4').activate();
}

function goToByDistrict() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  ss.setActiveSheet(ss.getSheetByName('By District'));
}
"""

for line_idx, line in enumerate(apps_script.strip().split("\n"), 17):
    cell = ws_as.cell(line_idx, 1)
    cell.value = line
    cell.font  = Font(name="Courier New", size=9, color="003300")

ws_as.column_dimensions["A"].width = 90
ws_as.sheet_properties.tabColor    = "888888"

# ============================================================
# Save
# ============================================================
out_path = os.path.join(base, "Indiana_County_Candidates_2026.xlsx")
wb.save(out_path)
print(f"Saved: {out_path}")
print(f"Data rows : {len(rows)}")
print(f"Counties  : {len(all_counties)}")
print()
print("Import into Google Sheets:")
print("  File → Import → Upload → select this file → 'Replace spreadsheet'")
print("  OR drag the file onto drive.google.com and open with Google Sheets.")
