"""
Build an interactive Google Sheets workbook: County → Candidates lookup.
Includes 2026 primary results: winner flag, vote totals, result ordering.

Import the output .xlsx into Google Sheets (File → Import, or open from Drive).

Sheets produced:
  County Lookup  – dropdown (92 counties) + QUERY formula shows all candidates
                   with result (Won / Lost / Uncontested) and vote totals
  By District    – flat reference table with auto-filter
  All Data       – hidden source table (powering QUERY formula)
  Apps Script    – Google Apps Script code + setup instructions
"""

import csv
import json
import os
import re
import collections
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import FormulaRule

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
BLUE_DARK   = "0C2340"
BLUE_MID    = "1E4488"
GOLD        = "C8962E"
GOLD_LIGHT  = "F5DFA0"
WHITE       = "FFFFFF"
GREY_LIGHT  = "F2F4F7"
GREY_MED    = "D0D5DD"
RED_LIGHT   = "FFE4E4"
BLUE_LIGHT  = "E4EEFF"
GREEN_LIGHT = "E4F5E4"
WIN_FILL    = "D4EDDA"   # soft green  – won primary
LOSS_FILL   = "F8F9FA"   # near-white  – lost primary

def thin(top=True, bottom=True, left=True, right=True):
    sides = {n: Side(style="thin", color=GREY_MED) if f else Side(style=None)
             for n, f in [("top",top),("bottom",bottom),("left",left),("right",right)]}
    return Border(**sides)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_CSV  = os.path.join(base, "AllOfficeResults(3).csv")
CANDS_JSON   = os.path.join(base, "data", "candidates_2026.json")
DISTRICT_JSON= os.path.join(base, "data", "district_data.json")

# ---------------------------------------------------------------------------
# Load JSON data
# ---------------------------------------------------------------------------
with open(CANDS_JSON) as f:
    cands_json = json.load(f)
with open(DISTRICT_JSON) as f:
    dm = json.load(f)

# ---------------------------------------------------------------------------
# Parse primary results CSV → determine winners
# ---------------------------------------------------------------------------
ORDINALS = {
    "first":1,"second":2,"third":3,"fourth":4,"fifth":5,
    "sixth":6,"seventh":7,"eighth":8,"ninth":9,
}

def office_to_key(office: str):
    """Return (dtype, district_num) or None if not a target race."""
    o = office.strip()
    if "State Representative" in o:
        m = re.search(r"District\s+(\d+)", o)
        return ("hd", int(m.group(1))) if m else None
    if "State Senator" in o:
        m = re.search(r"District\s+(\d+)", o)
        return ("sd", int(m.group(1))) if m else None
    if "United States Representative" in o:
        m = re.search(r"(\w+)\s+District", o, re.I)
        if m:
            word = m.group(1).lower()
            if word.isdigit():
                return ("cd", int(word))
            return ("cd", ORDINALS.get(word))
    return None

# Aggregate total votes per (dtype, dnum, party, name)
vote_totals = collections.defaultdict(int)
seats_map   = {}

with open(RESULTS_CSV, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        key = office_to_key(row["Office"])
        if key is None:
            continue
        dtype, dnum = key
        party = row["PoliticalParty"].strip()
        name  = row["NameonBallot"].strip()
        votes = int(row["TotalVotes"] or 0)
        seats = int(row["NumberofOfficeSeats"] or 1)
        vote_totals[(dtype, dnum, party, name)] += votes
        seats_map[(dtype, dnum, party)] = seats

# Normalise name for fuzzy matching (lowercase, collapse spaces)
def norm(s):
    return re.sub(r"\s+", " ", s.lower().strip())

# Build winner set: top-N per (dtype, dnum, party) by vote total
# Key: (dtype, dnum, norm_name) → True
winners = set()
vote_map = {}   # (dtype, dnum, norm_name) → total_votes

# Group by (dtype, dnum, party)
by_race = collections.defaultdict(list)
for (dtype, dnum, party, name), votes in vote_totals.items():
    by_race[(dtype, dnum, party)].append((name, votes))

for (dtype, dnum, party), candidates in by_race.items():
    n = seats_map.get((dtype, dnum, party), 1)
    ranked = sorted(candidates, key=lambda x: -x[1])
    for i in range(min(n, len(ranked))):
        winners.add((dtype, dnum, norm(ranked[i][0])))
    for name, votes in candidates:
        vote_map[(dtype, dnum, norm(name))] = votes

def candidate_result(dtype, dnum, name):
    """Return (result_label, result_sort_order, vote_total)."""
    # Check if there were any results for this race
    race_has_results = any(
        (dtype, dnum, p) in seats_map for p in ("Democratic","Republican","Libertarian","Independent")
    )
    if not race_has_results:
        return ("Uncontested", 2, 0)

    nkey = (dtype, dnum, norm(name))
    votes = vote_map.get(nkey, 0)

    # If no votes recorded for this candidate, mark uncontested
    if votes == 0:
        return ("Uncontested", 2, 0)

    if nkey in winners:
        return ("Won Primary ✓", 0, votes)
    return ("Lost Primary", 1, votes)

# ---------------------------------------------------------------------------
# Build flat rows:
# (county, sort_order, type, dist_num, dist_label, candidate, party,
#  result, result_sort, votes)
# ---------------------------------------------------------------------------
TYPE_ORDER = {"House": 1, "Senate": 2, "Congressional": 3}
JSON_DTYPE = {"House": "hd", "Senate": "sd", "Congressional": "cd"}

rows = []
for county in sorted(dm["all_counties"]):
    for hd in sorted(dm["county_to_hds"].get(county, [])):
        for c in cands_json.get("hd", {}).get(str(hd), []):
            result, rsort, votes = candidate_result("hd", hd, c["name"])
            rows.append((county, 1, "House", hd, f"HD-{hd}",
                         c["name"], c["party"], result, rsort, votes))
    for sd in sorted(dm["county_to_sds"].get(county, [])):
        for c in cands_json.get("sd", {}).get(str(sd), []):
            result, rsort, votes = candidate_result("sd", sd, c["name"])
            rows.append((county, 2, "Senate", sd, f"SD-{sd}",
                         c["name"], c["party"], result, rsort, votes))
    for cd in sorted(dm["county_to_cds"].get(county, [])):
        for c in cands_json.get("cd", {}).get(str(cd), []):
            result, rsort, votes = candidate_result("cd", cd, c["name"])
            rows.append((county, 3, "Congressional", cd, f"CD-{cd}",
                         c["name"], c["party"], result, rsort, votes))

all_counties = sorted(dm["all_counties"])
last_data_row = len(rows) + 1

# Sanity check
won_count = sum(1 for r in rows if "Won" in r[7])
print(f"Rows: {len(rows)} | Winners flagged: {won_count}")

# ---------------------------------------------------------------------------
wb = Workbook()
wb.remove(wb.active)

# ============================================================
# Sheet: All Data  (hidden — QUERY source)
# A=County  B=SortOrder  C=Type  D=Num  E=District
# F=Candidate  G=Party  H=Result  I=ResultSort  J=Votes
# ============================================================
ws_data = wb.create_sheet("All Data")
ws_data.sheet_state = "hidden"

DATA_HEADERS = ["County","SortOrder","Type","Num","District",
                "Candidate","Party","Result","ResultSort","Votes"]
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
ws_data.column_dimensions["H"].width = 18
ws_data.column_dimensions["I"].width = 12
ws_data.column_dimensions["J"].width = 10

# ============================================================
# Sheet: County Lookup  (tab 1 — main interactive sheet)
# ============================================================
ws_lu = wb.create_sheet("County Lookup", 0)

# ---- Banner ----
ws_lu.merge_cells("A1:I1")
banner = ws_lu["A1"]
banner.value     = "Indiana 2026 Primary Results — County Lookup"
banner.font      = Font(bold=True, size=16, color=WHITE)
banner.fill      = PatternFill("solid", fgColor=BLUE_DARK)
banner.alignment = Alignment(horizontal="center", vertical="center")
ws_lu.row_dimensions[1].height = 38

ws_lu.merge_cells("A2:I2")
sub = ws_lu["A2"]
sub.value     = "Select a county from the dropdown to view all 2026 primary candidates and results for that county's House, Senate, and Congressional districts."
sub.font      = Font(size=10, color=BLUE_DARK, italic=True)
sub.fill      = PatternFill("solid", fgColor=GOLD_LIGHT)
sub.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
ws_lu.row_dimensions[2].height = 28

ws_lu.row_dimensions[3].height = 8

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
ws_lu.row_dimensions[5].height = 8

ws_lu.merge_cells("B6:C6")
ws_lu["B6"].value     = "Candidates found:"
ws_lu["B6"].font      = Font(size=10, color=BLUE_DARK)
ws_lu["B6"].alignment = Alignment(horizontal="right", vertical="center")
ws_lu["D6"].value     = "=IFERROR(COUNTA(F9:F2000),0)"
ws_lu["D6"].font      = Font(bold=True, size=10, color=BLUE_DARK)
ws_lu["D6"].alignment = Alignment(horizontal="center")
ws_lu.row_dimensions[6].height = 20

ws_lu.merge_cells("E6:F6")
ws_lu["E6"].value     = "  ■ Won Primary ✓   ■ Lost Primary   ■ Uncontested"
ws_lu["E6"].font      = Font(size=9, color="555555", italic=True)
ws_lu["E6"].alignment = Alignment(vertical="center")

ws_lu.row_dimensions[7].height = 8

# ---- Results header row ----
result_cols    = ["B",       "C",      "D",      "E",               "F",     "G",              "H"]
result_headers = ["District","Type",   "Dist #", "Candidate Name",  "Party", "Primary Result", "Votes"]

for col_letter, hdr in zip(result_cols, result_headers):
    cell = ws_lu[f"{col_letter}8"]
    cell.value     = hdr
    cell.font      = Font(bold=True, size=11, color=WHITE)
    cell.fill      = PatternFill("solid", fgColor=BLUE_MID)
    cell.alignment = Alignment(horizontal="center", vertical="center")
    cell.border    = thin()
ws_lu.row_dimensions[8].height = 24

# ---- QUERY formula ----
# All Data: A=County B=SortOrder C=Type D=Num E=District F=Candidate G=Party H=Result I=ResultSort J=Votes
# SELECT District(E), Type(C), Num(D), Candidate(F), Party(G), Result(H), Votes(J)
# ORDER BY SortOrder(B) ASC, Num(D) ASC, ResultSort(I) ASC, Votes(J) DESC
query_formula = (
    "=IFERROR("
    "QUERY('All Data'!A:J,"
    "\"SELECT E, C, D, F, G, H, J "
    "WHERE A = '\"&D4&\"' "
    "ORDER BY B ASC, D ASC, I ASC, J DESC\","
    "1),"
    "{\"No candidates found for this county.\",\"\",\"\",\"\",\"\",\"\",\"\"})"
)
ws_lu["B9"].value = query_formula

# ---- Conditional formatting ----
# Party column G: D=red, R=blue, other=green
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

# Result column H: Won=green, Lost=grey
ws_lu.conditional_formatting.add(
    "G9:G2000",
    FormulaRule(formula=['LEFT($G9,3)="Won"'],
                fill=PatternFill("solid", fgColor=WIN_FILL),
                font=Font(color="155724", bold=True)),
)
ws_lu.conditional_formatting.add(
    "G9:G2000",
    FormulaRule(formula=['LEFT($G9,4)="Lost"'],
                fill=PatternFill("solid", fgColor=LOSS_FILL),
                font=Font(color="888888")),
)

# ---- Column widths ----
ws_lu.column_dimensions["A"].width = 3
ws_lu.column_dimensions["B"].width = 12
ws_lu.column_dimensions["C"].width = 16
ws_lu.column_dimensions["D"].width = 9
ws_lu.column_dimensions["E"].width = 40
ws_lu.column_dimensions["F"].width = 8
ws_lu.column_dimensions["G"].width = 18
ws_lu.column_dimensions["H"].width = 12
ws_lu.column_dimensions["I"].width = 3

ws_lu.freeze_panes = "B9"
ws_lu.sheet_properties.tabColor = GOLD

# ============================================================
# Sheet: By District  (sorted reference table)
# ============================================================
ws_bd = wb.create_sheet("By District")

ws_bd.merge_cells("A1:H1")
ws_bd["A1"].value     = "Indiana 2026 Primary Results — All Districts"
ws_bd["A1"].font      = Font(bold=True, size=14, color=WHITE)
ws_bd["A1"].fill      = PatternFill("solid", fgColor=BLUE_DARK)
ws_bd["A1"].alignment = Alignment(horizontal="center", vertical="center")
ws_bd.row_dimensions[1].height = 30

bd_hdrs = ["County","District","Type","Dist #","Candidate Name","Party","Primary Result","Votes"]
ws_bd.append(bd_hdrs)
for col, hdr in enumerate(bd_hdrs, 1):
    cell = ws_bd.cell(2, col)
    cell.font      = Font(bold=True, size=10, color=WHITE)
    cell.fill      = PatternFill("solid", fgColor=BLUE_MID)
    cell.alignment = Alignment(horizontal="center")
    cell.border    = thin()
ws_bd.row_dimensions[2].height = 20

sorted_rows = sorted(rows, key=lambda r: (r[1], r[3], r[8], -r[9], r[0], r[5]))
for idx, r in enumerate(sorted_rows, 3):
    county, _order, dtype, dnum, dlabel, cand, party, result, rsort, votes = r
    vals = [county, dlabel, dtype, dnum, cand, party, result, votes]
    bg = GREY_LIGHT if idx % 2 == 0 else WHITE
    for col, val in enumerate(vals, 1):
        cell = ws_bd.cell(idx, col)
        cell.value     = val
        cell.fill      = PatternFill("solid", fgColor=bg)
        cell.alignment = Alignment(vertical="center")
        cell.border    = thin()
    # Party colour
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
    # Result colour
    rcell = ws_bd.cell(idx, 7)
    if "Won" in result:
        rcell.fill = PatternFill("solid", fgColor=WIN_FILL)
        rcell.font = Font(color="155724", bold=True, size=10)
    elif "Lost" in result:
        rcell.fill = PatternFill("solid", fgColor=LOSS_FILL)
        rcell.font = Font(color="888888", size=10)

ws_bd.column_dimensions["A"].width = 18
ws_bd.column_dimensions["B"].width = 10
ws_bd.column_dimensions["C"].width = 15
ws_bd.column_dimensions["D"].width = 8
ws_bd.column_dimensions["E"].width = 40
ws_bd.column_dimensions["F"].width = 8
ws_bd.column_dimensions["G"].width = 18
ws_bd.column_dimensions["H"].width = 12
ws_bd.freeze_panes = "A3"
ws_bd.auto_filter.ref = f"A2:H{len(sorted_rows)+2}"
ws_bd.sheet_properties.tabColor = BLUE_MID

# ============================================================
# Sheet: Apps Script  (unchanged from previous version)
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
    ("A6",  "page title update, and a manual Refresh button in the IRS Tools menu."),
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

function onEdit(e) {
  const sheet = e.source.getActiveSheet();
  if (sheet.getName() !== 'County Lookup') return;
  if (e.range.getA1Notation() !== 'D4') return;

  const county = e.range.getValue();
  if (!county) return;

  e.source.toast(
    'Showing 2026 primary results for ' + county,
    'County Lookup',
    3
  );

  highlightSelector(sheet);
}

function highlightSelector(sheet) {
  const cell = sheet.getRange('D4');
  const original = cell.getBackground();
  cell.setBackground('#F5DFA0');
  SpreadsheetApp.flush();
  Utilities.sleep(300);
  cell.setBackground(original);
}

function refreshLookup() {
  const ss    = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName('County Lookup');
  if (!sheet) return;
  const cell   = sheet.getRange('D4');
  const county = cell.getValue();
  cell.clearContent();
  SpreadsheetApp.flush();
  cell.setValue(county);
  ss.toast('Refreshed: ' + county, 'County Lookup', 2);
}

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
print(f"Saved : {out_path}")
print(f"Rows  : {len(rows)}")
print(f"Won   : {won_count}")
print(f"Uncontested: {sum(1 for r in rows if r[7]=='Uncontested')}")
print()
print("Import into Google Sheets:")
print("  Drag onto drive.google.com → open with Google Sheets")
print("  OR File → Import → Upload → Replace spreadsheet")
