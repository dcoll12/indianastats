"""
Build Google Sheets county-candidates workbook — post-primary edition.

Changes from previous version:
  - Lost-primary candidates removed; only winners and uncontested shown
  - County Picker tab: checkboxes for all 92 counties (multi-select)
    Unchecked = show all counties; any checked = filter to those counties
  - District filter on Lookup tab: type dropdown + district-number input
  - FILTER formula combines all three filters dynamically

Sheets:
  Lookup         – main results sheet with filter controls
  County Picker  – 92-county checkbox selector
  By District    – full flat reference table (auto-filter)
  All Data       – hidden source table (winners / uncontested only)
  Apps Script    – onEdit script + Select All / Clear All helpers
"""

import csv, json, os, re, collections
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
WIN_FILL    = "D4EDDA"

def thin(top=True, bottom=True, left=True, right=True):
    s = {n: Side(style="thin", color=GREY_MED) if f else Side(style=None)
         for n, f in [("top",top),("bottom",bottom),("left",left),("right",right)]}
    return Border(**s)

def header_cell(cell, text, bg=BLUE_DARK, fg=WHITE, size=11, bold=True, center=True):
    cell.value     = text
    cell.font      = Font(bold=bold, size=size, color=fg)
    cell.fill      = PatternFill("solid", fgColor=bg)
    cell.alignment = Alignment(horizontal="center" if center else "left",
                               vertical="center", wrap_text=True)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
base         = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_CSV  = os.path.join(base, "AllOfficeResults(3).csv")
CANDS_JSON   = os.path.join(base, "data", "candidates_2026.json")
DISTRICT_JSON= os.path.join(base, "data", "district_data.json")

with open(CANDS_JSON) as f:  cands_json = json.load(f)
with open(DISTRICT_JSON) as f: dm = json.load(f)

# ---------------------------------------------------------------------------
# Parse CSV → determine winners
# ---------------------------------------------------------------------------
ORDINALS = {"first":1,"second":2,"third":3,"fourth":4,"fifth":5,
            "sixth":6,"seventh":7,"eighth":8,"ninth":9}

def office_to_key(office):
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
            w = m.group(1).lower()
            return ("cd", int(w) if w.isdigit() else ORDINALS.get(w))
    return None

vote_totals = collections.defaultdict(int)
seats_map   = {}
with open(RESULTS_CSV, newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        key = office_to_key(row["Office"])
        if not key: continue
        dtype, dnum = key
        party = row["PoliticalParty"].strip()
        name  = row["NameonBallot"].strip()
        vote_totals[(dtype, dnum, party, name)] += int(row["TotalVotes"] or 0)
        seats_map[(dtype, dnum, party)] = int(row["NumberofOfficeSeats"] or 1)

norm = lambda s: re.sub(r"\s+", " ", s.lower().strip())

winners  = set()
vote_map = {}
by_race  = collections.defaultdict(list)
for (dtype, dnum, party, name), votes in vote_totals.items():
    by_race[(dtype, dnum, party)].append((name, votes))
for (dtype, dnum, party), candidates in by_race.items():
    n = seats_map.get((dtype, dnum, party), 1)
    for cand_name, _ in sorted(candidates, key=lambda x: -x[1])[:n]:
        winners.add((dtype, dnum, norm(cand_name)))
    for cand_name, votes in candidates:
        vote_map[(dtype, dnum, norm(cand_name))] = votes

def candidate_result(dtype, dnum, name):
    """Return (result_label, result_sort, votes) — None means lost, skip it."""
    race_has_results = any(
        (dtype, dnum, p) in seats_map
        for p in ("Democratic", "Republican", "Libertarian", "Independent")
    )
    if not race_has_results:
        return ("Uncontested", 2, 0)
    nkey  = (dtype, dnum, norm(name))
    votes = vote_map.get(nkey, 0)
    if votes == 0:
        return ("Uncontested", 2, 0)
    if nkey in winners:
        return ("Won Primary ✓", 0, votes)
    return None   # lost — skip

# ---------------------------------------------------------------------------
# Build flat rows (winners + uncontested only):
# (county, sort_order, type, dist_num, dist_label, candidate, party,
#  result, result_sort, votes)
# ---------------------------------------------------------------------------
rows = []
for county in sorted(dm["all_counties"]):
    for hd in sorted(dm["county_to_hds"].get(county, [])):
        for c in cands_json.get("hd", {}).get(str(hd), []):
            r = candidate_result("hd", hd, c["name"])
            if r: rows.append((county, 1, "House", hd, f"HD-{hd}", c["name"], c["party"], *r))
    for sd in sorted(dm["county_to_sds"].get(county, [])):
        for c in cands_json.get("sd", {}).get(str(sd), []):
            r = candidate_result("sd", sd, c["name"])
            if r: rows.append((county, 2, "Senate", sd, f"SD-{sd}", c["name"], c["party"], *r))
    for cd in sorted(dm["county_to_cds"].get(county, [])):
        for c in cands_json.get("cd", {}).get(str(cd), []):
            r = candidate_result("cd", cd, c["name"])
            if r: rows.append((county, 3, "Congressional", cd, f"CD-{cd}", c["name"], c["party"], *r))

all_counties  = sorted(dm["all_counties"])
last_data_row = len(rows) + 1  # +1 for header
print(f"Rows after removing lost candidates: {len(rows)}")

# ---------------------------------------------------------------------------
wb = Workbook()
wb.remove(wb.active)

# ============================================================
# Sheet: All Data  (hidden — FILTER source)
# A=County  B=SortOrder  C=Type  D=Num  E=District
# F=Candidate  G=Party  H=Result  I=ResultSort  J=Votes
# ============================================================
ws_data = wb.create_sheet("All Data")
ws_data.sheet_state = "hidden"

DATA_HDRS = ["County","SortOrder","Type","Num","District",
             "Candidate","Party","Result","ResultSort","Votes"]
ws_data.append(DATA_HDRS)
for r in rows:
    ws_data.append(list(r))

for col, _ in enumerate(DATA_HDRS, 1):
    c = ws_data.cell(1, col)
    c.font      = Font(bold=True, color=WHITE, size=10)
    c.fill      = PatternFill("solid", fgColor=BLUE_DARK)
    c.alignment = Alignment(horizontal="center")

col_w = [18,10,16,6,10,35,8,18,10,12]
for i, w in enumerate(col_w, 1):
    ws_data.column_dimensions[ws_data.cell(1,i).column_letter].width = w

# ============================================================
# Sheet: County Picker
# Two-column checkbox layout; B5:B50 = counties 1-46, C5:C50 = checkboxes
# E5:E50 = counties 47-92,  F5:F50 = checkboxes
# ============================================================
ws_cp = wb.create_sheet("County Picker", 1)

ws_cp.merge_cells("A1:G1")
header_cell(ws_cp["A1"], "County Picker — Select Counties to Filter", size=14)
ws_cp.row_dimensions[1].height = 32

ws_cp.merge_cells("A2:G2")
sub = ws_cp["A2"]
sub.value     = ("Check counties to filter results on the Lookup tab.  "
                 "Leave ALL unchecked to show every county.  "
                 "Use the IRS Tools menu (Extensions → Apps Script → run onOpen first) "
                 "for Select All / Clear All buttons.")
sub.font      = Font(size=10, italic=True, color=BLUE_DARK)
sub.fill      = PatternFill("solid", fgColor=GOLD_LIGHT)
sub.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
ws_cp.row_dimensions[2].height = 36

ws_cp.row_dimensions[3].height = 8

# Column headers row 4
for col, text, bg in [("B","County",BLUE_MID), ("C","✓",BLUE_MID),
                       ("D","",BLUE_DARK),
                       ("E","County",BLUE_MID), ("F","✓",BLUE_MID)]:
    cell = ws_cp[f"{col}4"]
    cell.value     = text
    cell.font      = Font(bold=True, color=WHITE, size=10)
    cell.fill      = PatternFill("solid", fgColor=bg)
    cell.alignment = Alignment(horizontal="center", vertical="center")
ws_cp.row_dimensions[4].height = 20

# County data + checkboxes
half = 46   # 46 + 46 = 92
dv_check = DataValidation(type="list", formula1='"TRUE,FALSE"', allow_blank=False)
ws_cp.add_data_validation(dv_check)

for i, county in enumerate(all_counties):
    if i < half:
        row = 5 + i
        ws_cp.cell(row, 2).value = county   # B
        ws_cp.cell(row, 2).alignment = Alignment(vertical="center")
        ws_cp.cell(row, 2).font = Font(size=10)
        ws_cp.cell(row, 3).value = False    # C  (checkbox)
        ws_cp.cell(row, 3).alignment = Alignment(horizontal="center", vertical="center")
        dv_check.sqref = f"C5:C50 F5:F50"  # will be set after loop
    else:
        row = 5 + (i - half)
        ws_cp.cell(row, 5).value = county   # E
        ws_cp.cell(row, 5).alignment = Alignment(vertical="center")
        ws_cp.cell(row, 5).font = Font(size=10)
        ws_cp.cell(row, 6).value = False    # F  (checkbox)
        ws_cp.cell(row, 6).alignment = Alignment(horizontal="center", vertical="center")

# Alternating row shading
for i in range(half):
    row = 5 + i
    bg = GREY_LIGHT if i % 2 == 0 else WHITE
    for col in (2, 3, 5, 6):
        ws_cp.cell(row, col).fill = PatternFill("solid", fgColor=bg)

# Column widths
ws_cp.column_dimensions["A"].width = 2
ws_cp.column_dimensions["B"].width = 22
ws_cp.column_dimensions["C"].width = 6
ws_cp.column_dimensions["D"].width = 3
ws_cp.column_dimensions["E"].width = 22
ws_cp.column_dimensions["F"].width = 6
ws_cp.sheet_properties.tabColor = GOLD

# ============================================================
# Sheet: Lookup  (tab 0 — main interactive sheet)
# ============================================================
ws_lu = wb.create_sheet("Lookup", 0)

# ---- Banner ----
ws_lu.merge_cells("A1:J1")
header_cell(ws_lu["A1"], "Indiana 2026 Primary Winners — Candidate Lookup", size=16)
ws_lu.row_dimensions[1].height = 38

ws_lu.merge_cells("A2:J2")
sub2 = ws_lu["A2"]
sub2.value     = ("Use the filters below to look up primary winners by county and/or district.  "
                  "Select counties on the County Picker tab.  Leave district fields blank to see all.")
sub2.font      = Font(size=10, italic=True, color=BLUE_DARK)
sub2.fill      = PatternFill("solid", fgColor=GOLD_LIGHT)
sub2.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
ws_lu.row_dimensions[2].height = 28

ws_lu.row_dimensions[3].height = 8

# ---- Filter row 4 ----
#  B: "Counties:" label
#  C: count formula
#  D: note
#  F: "District Type:" label
#  G: type dropdown
#  H: "District #:" label
#  I: number input

ws_lu.row_dimensions[4].height = 30

# Counties section
ws_lu["B4"].value     = "Counties:"
ws_lu["B4"].font      = Font(bold=True, size=11, color=BLUE_DARK)
ws_lu["B4"].alignment = Alignment(horizontal="right", vertical="center")

ws_lu["C4"].value     = ("=LET(n, COUNTIF('County Picker'!C5:C50, TRUE)"
                          "+COUNTIF('County Picker'!F5:F50, TRUE),"
                          'IF(n=0,"All 92 counties",n&" of 92 selected"))')
ws_lu["C4"].font      = Font(bold=True, size=11, color=BLUE_DARK)
ws_lu["C4"].fill      = PatternFill("solid", fgColor=GOLD_LIGHT)
ws_lu["C4"].alignment = Alignment(horizontal="center", vertical="center")
ws_lu["C4"].border    = thin()

ws_lu["D4"].value     = "← see County Picker tab"
ws_lu["D4"].font      = Font(size=9, italic=True, color="888888")
ws_lu["D4"].alignment = Alignment(vertical="center")

# District type section
ws_lu["F4"].value     = "District Type:"
ws_lu["F4"].font      = Font(bold=True, size=11, color=BLUE_DARK)
ws_lu["F4"].alignment = Alignment(horizontal="right", vertical="center")

ws_lu["G4"].value     = "All Types"
ws_lu["G4"].font      = Font(bold=True, size=11, color=BLUE_DARK)
ws_lu["G4"].fill      = PatternFill("solid", fgColor=GOLD_LIGHT)
ws_lu["G4"].alignment = Alignment(horizontal="center", vertical="center")
ws_lu["G4"].border    = thin()

dv_type = DataValidation(
    type="list",
    formula1='"All Types,House,Senate,Congressional"',
    allow_blank=False,
    showDropDown=False,
)
dv_type.sqref = "G4"
ws_lu.add_data_validation(dv_type)

# District number section
ws_lu["H4"].value     = "District #:"
ws_lu["H4"].font      = Font(bold=True, size=11, color=BLUE_DARK)
ws_lu["H4"].alignment = Alignment(horizontal="right", vertical="center")

ws_lu["I4"].value     = ""   # user types a number here
ws_lu["I4"].fill      = PatternFill("solid", fgColor=GOLD_LIGHT)
ws_lu["I4"].alignment = Alignment(horizontal="center", vertical="center")
ws_lu["I4"].border    = thin()
ws_lu["I4"].font      = Font(bold=True, size=11, color=BLUE_DARK)

ws_lu.row_dimensions[5].height = 8

# ---- Candidate count row 6 ----
ws_lu.row_dimensions[6].height = 20
ws_lu["B6"].value     = "Candidates shown:"
ws_lu["B6"].font      = Font(size=10, color=BLUE_DARK)
ws_lu["B6"].alignment = Alignment(horizontal="right", vertical="center")
ws_lu["C6"].value     = "=IFERROR(COUNTA(F8:F5000),0)"
ws_lu["C6"].font      = Font(bold=True, size=10, color=BLUE_DARK)
ws_lu["C6"].alignment = Alignment(horizontal="center")

ws_lu["E6"].value     = "  ■ Won Primary ✓ (green)    ■ Uncontested (no fill)"
ws_lu["E6"].font      = Font(size=9, italic=True, color="555555")
ws_lu["E6"].alignment = Alignment(vertical="center")

ws_lu.row_dimensions[7].height = 8

# ---- Results header row 7 ----
RES_COLS = ["B",       "C",      "D",      "E",              "F",     "G",              "H"]
RES_HDRS = ["District","Type",   "Dist #", "Candidate Name", "Party", "Primary Result", "Votes"]
for col_letter, hdr in zip(RES_COLS, RES_HDRS):
    cell = ws_lu[f"{col_letter}7"]
    cell.value     = hdr
    cell.font      = Font(bold=True, size=11, color=WHITE)
    cell.fill      = PatternFill("solid", fgColor=BLUE_MID)
    cell.alignment = Alignment(horizontal="center", vertical="center")
    cell.border    = thin()
ws_lu.row_dimensions[7].height = 24

# ---- Main FILTER formula in B8 ----
# All Data cols: A=County B=SortOrder C=Type D=Num E=District F=Candidate G=Party H=Result I=ResultSort J=Votes
# County Picker:  B5:B50=counties left, C5:C50=checkboxes left
#                 E5:E50=counties right, F5:F50=checkboxes right
# Filter controls: G4=dist type,  I4=dist number
L = last_data_row
filter_formula = (
    "=IFERROR("
    "LET("
    # How many counties are checked?
    "checked,COUNTIF('County Picker'!C5:C50,TRUE)+COUNTIF('County Picker'!F5:F50,TRUE),"
    # county_match: TRUE for all rows when nothing checked; else membership test
    "county_match,IF(checked=0,TRUE,"
    "COUNTIF("
    "FILTER({'County Picker'!B5:B50;'County Picker'!E5:E50},"
    "{'County Picker'!C5:C50;'County Picker'!F5:F50}),"
    f"'All Data'!A2:A{L})>0),"
    # type_match: pass all when "All Types", else match column C
    f"type_match,(G4=\"All Types\")+('All Data'!C2:C{L}=G4)>0,"
    # num_match: pass all when I4 blank, else match column D (numeric)
    f"num_match,(LEN(TRIM(I4))=0)+('All Data'!D2:D{L}=IFERROR(VALUE(I4),0))>0,"
    # Apply all filters then sort by SortOrder, then Num, then Votes desc
    "SORT("
    "FILTER("
    f"{{'All Data'!E2:E{L},'All Data'!C2:C{L},'All Data'!D2:D{L},"
    f"'All Data'!F2:F{L},'All Data'!G2:G{L},'All Data'!H2:H{L},'All Data'!J2:J{L}}},"
    "county_match*type_match*num_match"
    "),"
    "{{1,3}},{{TRUE,TRUE}}"  # sort col 1 (District label) ASC then col 3 (Num) ASC
    ")),"
    '"No candidates match the selected filters."'
    ")"
)
ws_lu["B8"].value = filter_formula

# ---- Conditional formatting ----
# Party
ws_lu.conditional_formatting.add("F8:F5000",
    FormulaRule(formula=['$F8="D"'],
                fill=PatternFill("solid", fgColor=RED_LIGHT),
                font=Font(color="8B0000", bold=True)))
ws_lu.conditional_formatting.add("F8:F5000",
    FormulaRule(formula=['$F8="R"'],
                fill=PatternFill("solid", fgColor=BLUE_LIGHT),
                font=Font(color="00008B", bold=True)))
ws_lu.conditional_formatting.add("F8:F5000",
    FormulaRule(formula=['AND($F8<>"D",$F8<>"R",$F8<>"")'],
                fill=PatternFill("solid", fgColor=GREEN_LIGHT),
                font=Font(color="005500", bold=True)))
# Result
ws_lu.conditional_formatting.add("G8:G5000",
    FormulaRule(formula=['LEFT($G8,3)="Won"'],
                fill=PatternFill("solid", fgColor=WIN_FILL),
                font=Font(color="155724", bold=True)))

# ---- Column widths ----
ws_lu.column_dimensions["A"].width = 2
ws_lu.column_dimensions["B"].width = 12
ws_lu.column_dimensions["C"].width = 16
ws_lu.column_dimensions["D"].width = 9
ws_lu.column_dimensions["E"].width = 40
ws_lu.column_dimensions["F"].width = 8
ws_lu.column_dimensions["G"].width = 18
ws_lu.column_dimensions["H"].width = 12
ws_lu.column_dimensions["I"].width = 2

ws_lu.freeze_panes = "B8"
ws_lu.sheet_properties.tabColor = GOLD

# ============================================================
# Sheet: By District  (sorted reference table)
# ============================================================
ws_bd = wb.create_sheet("By District")

ws_bd.merge_cells("A1:H1")
header_cell(ws_bd["A1"], "Indiana 2026 Primary Winners — All Districts", size=14)
ws_bd.row_dimensions[1].height = 30

bd_hdrs = ["County","District","Type","Dist #","Candidate Name","Party","Primary Result","Votes"]
ws_bd.append(bd_hdrs)
for col, hdr in enumerate(bd_hdrs, 1):
    c = ws_bd.cell(2, col)
    c.font = Font(bold=True, size=10, color=WHITE)
    c.fill = PatternFill("solid", fgColor=BLUE_MID)
    c.alignment = Alignment(horizontal="center")
    c.border = thin()
ws_bd.row_dimensions[2].height = 20

sorted_rows = sorted(rows, key=lambda r: (r[1], r[3], r[8], -r[9], r[0], r[5]))
for idx, r in enumerate(sorted_rows, 3):
    county, _ord, dtype, dnum, dlabel, cand, party, result, rsort, votes = r
    vals = [county, dlabel, dtype, dnum, cand, party, result, votes]
    bg = GREY_LIGHT if idx % 2 == 0 else WHITE
    for col, val in enumerate(vals, 1):
        cell = ws_bd.cell(idx, col)
        cell.value     = val
        cell.fill      = PatternFill("solid", fgColor=bg)
        cell.alignment = Alignment(vertical="center")
        cell.border    = thin()
    # Party colour
    pc = ws_bd.cell(idx, 6)
    if party == "D":
        pc.fill = PatternFill("solid", fgColor=RED_LIGHT)
        pc.font = Font(color="8B0000", bold=True, size=10)
    elif party == "R":
        pc.fill = PatternFill("solid", fgColor=BLUE_LIGHT)
        pc.font = Font(color="00008B", bold=True, size=10)
    else:
        pc.fill = PatternFill("solid", fgColor=GREEN_LIGHT)
        pc.font = Font(color="005500", bold=True, size=10)
    # Result colour
    rc = ws_bd.cell(idx, 7)
    if "Won" in result:
        rc.fill = PatternFill("solid", fgColor=WIN_FILL)
        rc.font = Font(color="155724", bold=True, size=10)

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
# Sheet: Apps Script
# ============================================================
ws_as = wb.create_sheet("Apps Script")

ws_as.merge_cells("A1:G1")
header_cell(ws_as["A1"], "Google Apps Script — Setup Instructions + Full Code", size=13)
ws_as.row_dimensions[1].height = 28

notes = [
    ("A3",  "WHAT THIS SCRIPT ADDS:"),
    ("A4",  "• IRS Tools menu with Select All / Clear All county buttons"),
    ("A5",  "• Toast notification when filters change"),
    ("A6",  "• Quick navigation items (Go to Lookup / County Picker / By District)"),
    ("A8",  "HOW TO ADD:"),
    ("A9",  "1. Extensions → Apps Script"),
    ("A10", "2. Delete placeholder code, paste everything from row 17 onward"),
    ("A11", "3. Save (Ctrl+S), close the Apps Script tab, reload the spreadsheet"),
    ("A12", "4. You will see an IRS Tools menu appear in the menu bar"),
    ("A13", "5. Run IRS Tools → Select All or Clear All to bulk-toggle county checkboxes"),
    ("A15", "── APPS SCRIPT CODE BELOW ──"),
]
for addr, text in notes:
    cell = ws_as[addr]
    cell.value     = text
    cell.alignment = Alignment(wrap_text=True)
    cell.font = (Font(bold=True, size=11, color=BLUE_DARK) if addr in ("A3","A8")
                 else Font(bold=True, size=10, color=GOLD) if addr == "A15"
                 else Font(size=10))

apps_script = r"""
// ============================================================
// Paste this entire block into Extensions → Apps Script
// ============================================================

// ---- Menu ----
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('IRS Tools')
    .addItem('Select All Counties',  'selectAllCounties')
    .addItem('Clear All Counties',   'clearAllCounties')
    .addSeparator()
    .addItem('Reset District Filter','resetDistrictFilter')
    .addSeparator()
    .addItem('Go to Lookup',         'goToLookup')
    .addItem('Go to County Picker',  'goToCountyPicker')
    .addItem('Go to By District',    'goToByDistrict')
    .addToUi();
}

// ---- County helpers ----
function selectAllCounties() {
  const cp = SpreadsheetApp.getActiveSpreadsheet().getSheetByName('County Picker');
  if (!cp) return;
  cp.getRange('C5:C50').setValue(true);
  cp.getRange('F5:F50').setValue(true);
  SpreadsheetApp.getActiveSpreadsheet()
    .toast('All 92 counties selected.', 'IRS Tools', 3);
}

function clearAllCounties() {
  const cp = SpreadsheetApp.getActiveSpreadsheet().getSheetByName('County Picker');
  if (!cp) return;
  cp.getRange('C5:C50').setValue(false);
  cp.getRange('F5:F50').setValue(false);
  SpreadsheetApp.getActiveSpreadsheet()
    .toast('All counties cleared — showing all 92 counties.', 'IRS Tools', 3);
}

// ---- District filter reset ----
function resetDistrictFilter() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const lu = ss.getSheetByName('Lookup');
  if (!lu) return;
  lu.getRange('G4').setValue('All Types');
  lu.getRange('I4').clearContent();
  ss.toast('District filter reset.', 'IRS Tools', 2);
}

// ---- onEdit: toast when filters change ----
function onEdit(e) {
  const sheet = e.source.getActiveSheet();
  const addr  = e.range.getA1Notation();
  const ss    = e.source;

  // County Picker checkboxes
  if (sheet.getName() === 'County Picker') {
    if (e.range.getColumn() === 3 || e.range.getColumn() === 6) {
      const n = countChecked(sheet);
      ss.toast(
        n === 0 ? 'Showing all 92 counties.' : n + ' counties selected.',
        'County Filter', 3
      );
    }
    return;
  }

  // Lookup district filters
  if (sheet.getName() === 'Lookup') {
    if (addr === 'G4' || addr === 'I4') {
      const type = sheet.getRange('G4').getValue();
      const num  = sheet.getRange('I4').getValue();
      const msg  = 'Filter: ' +
        (type === 'All Types' ? 'All Types' : type) +
        (num ? ', District ' + num : '');
      ss.toast(msg, 'District Filter', 3);
    }
  }
}

function countChecked(cpSheet) {
  const left  = cpSheet.getRange('C5:C50').getValues().flat().filter(Boolean).length;
  const right = cpSheet.getRange('F5:F50').getValues().flat().filter(Boolean).length;
  return left + right;
}

// ---- Navigation ----
function goToLookup() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  ss.setActiveSheet(ss.getSheetByName('Lookup'));
}
function goToCountyPicker() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  ss.setActiveSheet(ss.getSheetByName('County Picker'));
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
won_rows = sum(1 for r in rows if "Won" in r[7])
unc_rows = sum(1 for r in rows if r[7] == "Uncontested")
print(f"Saved  : {out_path}")
print(f"Rows   : {len(rows)}  (Won: {won_rows}  Uncontested: {unc_rows})")
print()
print("Import: drag onto drive.google.com → open with Google Sheets")
print("        Then: Format the checkbox columns (C5:C50, F5:F50 on County Picker)")
print("        → select those cells → Format → Checkbox")
