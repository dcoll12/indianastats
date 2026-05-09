"""
Build an interactive Excel workbook: County → Candidates lookup.

Sheets produced:
  County Lookup  – main sheet; pick a county from the dropdown and see all candidates
  By District    – flat table sorted by district (for reference / pivot use)
  All Data       – hidden raw data table that powers the formulas / VBA
  VBA Setup      – copy-paste instructions + full VBA source for older Excel

The FILTER formula (Excel 365 / 2019+) drives instant updates on County Lookup.
The VBA Setup sheet contains macro code that works on Excel 2016 and older.
"""

import json
import os
from openpyxl import Workbook
from openpyxl.styles import (
    Font, PatternFill, Alignment, Border, Side, GradientFill
)
from openpyxl.utils import get_column_letter, quote_sheetname
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import CellIsRule, FormulaRule

# ---------------------------------------------------------------------------
# Colours / palette
# ---------------------------------------------------------------------------
BLUE_DARK  = "0C2340"   # Indiana dark navy
BLUE_MID   = "1E4488"   # mid blue
GOLD       = "C8962E"   # Indiana gold
GOLD_LIGHT = "F5DFA0"   # soft gold for highlights
WHITE      = "FFFFFF"
GREY_LIGHT = "F2F4F7"
GREY_MED   = "D0D5DD"
RED_LIGHT  = "FFE4E4"   # D-party fill
BLUE_LIGHT = "E4EEFF"   # R-party fill
GREEN_LIGHT= "E4F5E4"   # Independent / other

# ---------------------------------------------------------------------------
# Helper: thin border
# ---------------------------------------------------------------------------
def thin_border(top=True, bottom=True, left=True, right=True):
    sides = {}
    for name, flag in [("top", top), ("bottom", bottom),
                       ("left", left),  ("right", right)]:
        sides[name] = Side(style="thin", color=GREY_MED) if flag else Side(style=None)
    return Border(**sides)

def thick_bottom():
    return Border(bottom=Side(style="medium", color=BLUE_DARK))

# ---------------------------------------------------------------------------
# Load source data
# ---------------------------------------------------------------------------
base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

with open(os.path.join(base, "data", "candidates_2026.json")) as f:
    cands = json.load(f)

with open(os.path.join(base, "data", "district_data.json")) as f:
    dm = json.load(f)

# ---------------------------------------------------------------------------
# Build flat rows: (county, dist_type, dist_num, dist_label, candidate, party)
# ---------------------------------------------------------------------------
TYPE_ORDER = {"House": 1, "Senate": 2, "Congressional": 3}
TYPE_ABBR  = {"House": "HD", "Senate": "SD", "Congressional": "CD"}

rows = []
for county in sorted(dm["all_counties"]):
    hds = dm["county_to_hds"].get(county, [])
    sds = dm["county_to_sds"].get(county, [])
    cds = dm["county_to_cds"].get(county, [])

    for hd in sorted(hds):
        for c in cands.get("hd", {}).get(str(hd), []):
            rows.append((county, "House", hd, f"HD-{hd}", c["name"], c["party"]))
    for sd in sorted(sds):
        for c in cands.get("sd", {}).get(str(sd), []):
            rows.append((county, "Senate", sd, f"SD-{sd}", c["name"], c["party"]))
    for cd in sorted(cds):
        for c in cands.get("cd", {}).get(str(cd), []):
            rows.append((county, "Congressional", cd, f"CD-{cd}", c["name"], c["party"]))

all_counties = sorted(dm["all_counties"])

# ---------------------------------------------------------------------------
# Create workbook
# ---------------------------------------------------------------------------
wb = Workbook()

# Remove default sheet
wb.remove(wb.active)

# ============================================================
# Sheet 1 – All Data (hidden, used as data source)
# ============================================================
ws_data = wb.create_sheet("All Data")
ws_data.sheet_state = "hidden"

HEADERS = ["County", "Dist Type", "Dist #", "District", "Candidate Name", "Party"]
ws_data.append(HEADERS)

for row in rows:
    ws_data.append(list(row))

# Style header
for col, _ in enumerate(HEADERS, 1):
    cell = ws_data.cell(row=1, column=col)
    cell.font       = Font(bold=True, color=WHITE, size=10)
    cell.fill       = PatternFill("solid", fgColor=BLUE_DARK)
    cell.alignment  = Alignment(horizontal="center")

ws_data.column_dimensions["A"].width = 18
ws_data.column_dimensions["B"].width = 16
ws_data.column_dimensions["C"].width = 8
ws_data.column_dimensions["D"].width = 10
ws_data.column_dimensions["E"].width = 35
ws_data.column_dimensions["F"].width = 10

# Named range for county list (A2:A{last}) – used by dropdown
last_data_row = len(rows) + 1
ws_data.title = "All Data"

# ============================================================
# Sheet 2 – County Lookup (main interactive sheet)
# ============================================================
ws_lu = wb.create_sheet("County Lookup", 0)  # first tab

# ---- Banner ----
ws_lu.merge_cells("A1:H1")
banner = ws_lu["A1"]
banner.value     = "Indiana 2026 Primary Candidates — County Lookup"
banner.font      = Font(bold=True, size=16, color=WHITE)
banner.fill      = PatternFill("solid", fgColor=BLUE_DARK)
banner.alignment = Alignment(horizontal="center", vertical="center")
ws_lu.row_dimensions[1].height = 36

ws_lu.merge_cells("A2:H2")
sub = ws_lu["A2"]
sub.value     = "Select a county below to view all 2026 primary candidates in that county's House, Senate, and Congressional districts."
sub.font      = Font(size=10, color=BLUE_DARK, italic=True)
sub.fill      = PatternFill("solid", fgColor=GOLD_LIGHT)
sub.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
ws_lu.row_dimensions[2].height = 28

# ---- County selector row ----
ws_lu.row_dimensions[3].height = 6   # spacer

ws_lu.merge_cells("B4:C4")
label = ws_lu["B4"]
label.value     = "Select County:"
label.font      = Font(bold=True, size=12, color=BLUE_DARK)
label.alignment = Alignment(horizontal="right", vertical="center")

selector = ws_lu["D4"]
selector.value     = all_counties[0]   # default to Adams
selector.font      = Font(bold=True, size=12, color=BLUE_DARK)
selector.fill      = PatternFill("solid", fgColor=GOLD_LIGHT)
selector.alignment = Alignment(horizontal="center", vertical="center")
selector.border    = thin_border()
ws_lu.row_dimensions[4].height = 26

# Data validation dropdown for D4
county_list_str = ",".join(all_counties)
dv = DataValidation(
    type="list",
    formula1=f'"{ county_list_str }"',
    allow_blank=False,
    showDropDown=False,
    showErrorMessage=True,
    error="Please select a valid Indiana county.",
    errorTitle="Invalid County"
)
dv.sqref = "D4"
ws_lu.add_data_validation(dv)

# ---- Column count indicator ----
ws_lu.row_dimensions[5].height = 6   # spacer

ws_lu.merge_cells("B6:C6")
ws_lu["B6"].value     = "Total candidates:"
ws_lu["B6"].font      = Font(size=10, color=BLUE_DARK)
ws_lu["B6"].alignment = Alignment(horizontal="right")

# COUNTA of the spill range gives count; we reference the results table (row 9+)
ws_lu["D6"].value     = '=IFERROR(COUNTA(B9#),0)'
ws_lu["D6"].font      = Font(bold=True, size=10, color=BLUE_DARK)
ws_lu["D6"].alignment = Alignment(horizontal="center")

ws_lu.row_dimensions[6].height = 20
ws_lu.row_dimensions[7].height = 6   # spacer

# ---- Results table header ----
result_headers = ["District", "Type", "Dist #", "Candidate Name", "Party"]
result_cols    = ["B",        "C",    "D",      "E",              "F"]

for col_letter, hdr in zip(result_cols, result_headers):
    cell = ws_lu[f"{col_letter}8"]
    cell.value     = hdr
    cell.font      = Font(bold=True, size=11, color=WHITE)
    cell.fill      = PatternFill("solid", fgColor=BLUE_MID)
    cell.alignment = Alignment(horizontal="center", vertical="center")
    cell.border    = thin_border()
ws_lu.row_dimensions[8].height = 22

# ---- FILTER formula in B9 (Excel 365 / 2019+) ----
# FILTER returns multiple columns; we sort by district type order then number.
# Layout: District label | Type | Dist# | Candidate | Party
# All Data columns: A=County B=DistType C=DistNum D=District E=Candidate F=Party
filter_formula = (
    '=IFERROR('
    'LET('
    '  src, FILTER(\'All Data\'!A2:F{last},'
    '               \'All Data\'!A2:A{last}=D4,'
    '               "No candidates found for this county."),'
    '  SORT(CHOOSE({{4,2,3,5,6}},src),{{1,2}},{{1,1}})'
    '),'
    '"No candidates found for this county."'
    ')'
).format(last=last_data_row)

ws_lu["B9"].value = filter_formula

# ---- Conditional formatting for Party (column F = col 6) ----
# D = Democrat → light red; R = Republican → light blue; other → light green
ws_lu.conditional_formatting.add(
    "F9:F2000",
    FormulaRule(
        formula=['$F9="D"'],
        fill=PatternFill("solid", fgColor=RED_LIGHT),
        font=Font(color="8B0000", bold=True)
    )
)
ws_lu.conditional_formatting.add(
    "F9:F2000",
    FormulaRule(
        formula=['$F9="R"'],
        fill=PatternFill("solid", fgColor=BLUE_LIGHT),
        font=Font(color="00008B", bold=True)
    )
)
ws_lu.conditional_formatting.add(
    "F9:F2000",
    FormulaRule(
        formula=['AND($F9<>"D",$F9<>"R",$F9<>"")'],
        fill=PatternFill("solid", fgColor=GREEN_LIGHT),
        font=Font(color="005500", bold=True)
    )
)

# ---- Column widths ----
ws_lu.column_dimensions["A"].width = 3   # left margin
ws_lu.column_dimensions["B"].width = 12  # District label
ws_lu.column_dimensions["C"].width = 16  # Type
ws_lu.column_dimensions["D"].width = 9   # Dist #
ws_lu.column_dimensions["E"].width = 38  # Candidate Name
ws_lu.column_dimensions["F"].width = 8   # Party
ws_lu.column_dimensions["G"].width = 3   # right margin

# ---- Freeze panes below header + row 8 ----
ws_lu.freeze_panes = "B9"

# ---- Print setup ----
ws_lu.page_setup.orientation    = "portrait"
ws_lu.page_setup.fitToPage      = True
ws_lu.page_setup.fitToWidth     = 1
ws_lu.sheet_properties.tabColor = GOLD

# ============================================================
# Sheet 3 – By District (sorted reference table)
# ============================================================
ws_bd = wb.create_sheet("By District")

# Banner
ws_bd.merge_cells("A1:F1")
ws_bd["A1"].value     = "Indiana 2026 Primary Candidates — All Districts"
ws_bd["A1"].font      = Font(bold=True, size=14, color=WHITE)
ws_bd["A1"].fill      = PatternFill("solid", fgColor=BLUE_DARK)
ws_bd["A1"].alignment = Alignment(horizontal="center", vertical="center")
ws_bd.row_dimensions[1].height = 30

bd_headers = ["County", "District", "Type", "Dist #", "Candidate Name", "Party"]
ws_bd.append(bd_headers)
for col, hdr in enumerate(bd_headers, 1):
    cell = ws_bd.cell(row=2, column=col)
    cell.font      = Font(bold=True, size=10, color=WHITE)
    cell.fill      = PatternFill("solid", fgColor=BLUE_MID)
    cell.alignment = Alignment(horizontal="center")
    cell.border    = thin_border()
ws_bd.row_dimensions[2].height = 20

# Sort rows by dist type order, then dist num, then candidate
def sort_key(r):
    return (TYPE_ORDER.get(r[1], 9), r[2], r[0], r[4])

sorted_rows = sorted(rows, key=sort_key)

for idx, r in enumerate(sorted_rows, 3):
    county, dtype, dnum, dlabel, cand, party = r
    ws_bd.cell(row=idx, column=1).value = county
    ws_bd.cell(row=idx, column=2).value = dlabel
    ws_bd.cell(row=idx, column=3).value = dtype
    ws_bd.cell(row=idx, column=4).value = dnum
    ws_bd.cell(row=idx, column=5).value = cand
    ws_bd.cell(row=idx, column=6).value = party
    fill_color = GREY_LIGHT if idx % 2 == 0 else WHITE
    for col in range(1, 7):
        cell = ws_bd.cell(row=idx, column=col)
        cell.fill      = PatternFill("solid", fgColor=fill_color)
        cell.alignment = Alignment(vertical="center")
        cell.border    = thin_border()
    # Party highlight
    pcell = ws_bd.cell(row=idx, column=6)
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
ws_bd.column_dimensions["E"].width = 38
ws_bd.column_dimensions["F"].width = 8

ws_bd.freeze_panes = "A3"
ws_bd.auto_filter.ref = f"A2:F{len(sorted_rows)+2}"
ws_bd.sheet_properties.tabColor = BLUE_MID

# ============================================================
# Sheet 4 – VBA Setup (instructions + full VBA source)
# ============================================================
ws_vba = wb.create_sheet("VBA Setup")

ws_vba.merge_cells("A1:G1")
ws_vba["A1"].value     = "VBA Macro Setup — For Excel 2016 / Older Excel Without FILTER Function"
ws_vba["A1"].font      = Font(bold=True, size=13, color=WHITE)
ws_vba["A1"].fill      = PatternFill("solid", fgColor=BLUE_DARK)
ws_vba["A1"].alignment = Alignment(horizontal="center", vertical="center")
ws_vba.row_dimensions[1].height = 28

instructions = [
    ("A3",  "IF THE COUNTY LOOKUP TAB SHOWS A FORMULA ERROR:"),
    ("A4",  "Your version of Excel does not support the FILTER function (requires Excel 365 or Excel 2019+)."),
    ("A5",  "Follow the steps below to enable the VBA macro version instead."),
    ("A7",  "HOW TO ADD THE MACRO:"),
    ("A8",  "1. Press Alt + F11 to open the Visual Basic Editor (VBE)."),
    ("A9",  "2. In the Project Explorer (left panel), expand this workbook."),
    ("A10", "3. Double-click on 'Sheet1 (County Lookup)' to open its code window."),
    ("A11", "4. Copy ALL of the VBA code from rows 16 onward and paste it into that window."),
    ("A12", "5. Close the VBE (Alt + F4 or click the X)."),
    ("A13", "6. Save the file as a Macro-Enabled Workbook (.xlsm) when prompted."),
    ("A14", "7. Now selecting a county from the dropdown on 'County Lookup' will auto-populate the list."),
]

for addr, text in instructions:
    cell = ws_vba[addr]
    cell.value     = text
    cell.alignment = Alignment(wrap_text=True)
    if addr in ("A3", "A7"):
        cell.font = Font(bold=True, size=11, color=BLUE_DARK)
    elif addr in ("A4", "A5"):
        cell.font = Font(size=10, italic=True, color="444444")
    else:
        cell.font = Font(size=10)

ws_vba["A15"].value = "── VBA CODE BELOW ──"
ws_vba["A15"].font  = Font(bold=True, size=10, color=GOLD)

# Build the complete VBA source as a string
vba_code = r"""
' ============================================================
' Paste this ENTIRE block into the Sheet Code module for
' "County Lookup" (not a standard module — Sheet1 module).
' ============================================================

Private Sub Worksheet_Change(ByVal Target As Range)
    ' Auto-fire when the county dropdown (D4) changes
    If Not Intersect(Target, Me.Range("D4")) Is Nothing Then
        Application.EnableEvents = False
        Application.ScreenUpdating = False
        Call RefreshCandidates
        Application.ScreenUpdating = True
        Application.EnableEvents = True
    End If
End Sub

Sub RefreshCandidates()
    Dim wsLookup  As Worksheet
    Dim wsData    As Worksheet
    Dim county    As String
    Dim lastData  As Long
    Dim outRow    As Long
    Dim i         As Long

    Set wsLookup = ThisWorkbook.Sheets("County Lookup")
    Set wsData   = ThisWorkbook.Sheets("All Data")

    county = Trim(wsLookup.Range("D4").Value)

    ' Clear previous results (B9 onward, columns B:F)
    Dim clearRange As Range
    Set clearRange = wsLookup.Range("B9:F2000")
    clearRange.ClearContents
    clearRange.Interior.ColorIndex = xlNone
    clearRange.Font.Bold = False

    If county = "" Then
        wsLookup.Range("D6").Value = 0
        Exit Sub
    End If

    lastData = wsData.Cells(wsData.Rows.Count, "A").End(xlUp).Row
    outRow   = 9

    ' Collect matching rows
    Dim results() As Variant
    Dim count     As Long
    count = 0
    ReDim results(1 To lastData, 1 To 5)

    For i = 2 To lastData
        If wsData.Cells(i, 1).Value = county Then
            count = count + 1
            results(count, 1) = wsData.Cells(i, 4).Value  ' District label
            results(count, 2) = wsData.Cells(i, 2).Value  ' Type
            results(count, 3) = wsData.Cells(i, 3).Value  ' Dist #
            results(count, 4) = wsData.Cells(i, 5).Value  ' Candidate
            results(count, 5) = wsData.Cells(i, 6).Value  ' Party
        End If
    Next i

    If count = 0 Then
        wsLookup.Range("B9").Value = "No candidates found for " & county
        wsLookup.Range("D6").Value = 0
        Exit Sub
    End If

    ' Write results
    Dim altRow As Boolean
    altRow = False
    For i = 1 To count
        Dim baseCol As Long
        Dim r As Long
        r = outRow + i - 1
        altRow = (i Mod 2 = 0)

        Dim bgColor As Long
        If altRow Then
            bgColor = RGB(242, 244, 247)
        Else
            bgColor = RGB(255, 255, 255)
        End If

        wsLookup.Cells(r, 2).Value = results(i, 1)  ' District label
        wsLookup.Cells(r, 3).Value = results(i, 2)  ' Type
        wsLookup.Cells(r, 4).Value = results(i, 3)  ' Dist #
        wsLookup.Cells(r, 5).Value = results(i, 4)  ' Candidate
        wsLookup.Cells(r, 6).Value = results(i, 5)  ' Party

        ' Row background
        For c = 2 To 6
            wsLookup.Cells(r, c).Interior.Color = bgColor
        Next c

        ' Party colour coding
        Dim party As String
        party = results(i, 5)
        If party = "D" Then
            wsLookup.Cells(r, 6).Interior.Color = RGB(255, 228, 228)
            wsLookup.Cells(r, 6).Font.Color = RGB(139, 0, 0)
            wsLookup.Cells(r, 6).Font.Bold = True
        ElseIf party = "R" Then
            wsLookup.Cells(r, 6).Interior.Color = RGB(228, 238, 255)
            wsLookup.Cells(r, 6).Font.Color = RGB(0, 0, 139)
            wsLookup.Cells(r, 6).Font.Bold = True
        Else
            wsLookup.Cells(r, 6).Interior.Color = RGB(228, 245, 228)
            wsLookup.Cells(r, 6).Font.Color = RGB(0, 85, 0)
            wsLookup.Cells(r, 6).Font.Bold = True
        End If
    Next i

    wsLookup.Range("D6").Value = count
End Sub

' ---- Optional: Add a refresh button macro ----
Sub RunRefreshButton()
    Call RefreshCandidates
End Sub
"""

# Write VBA code line by line starting at row 16
for line_idx, line in enumerate(vba_code.strip().split("\n"), 16):
    cell = ws_vba.cell(row=line_idx, column=1)
    cell.value = line
    cell.font  = Font(name="Courier New", size=9, color="003300")

ws_vba.column_dimensions["A"].width = 100
ws_vba.sheet_properties.tabColor    = "888888"

# ============================================================
# Output
# ============================================================
out_path = os.path.join(base, "Indiana_County_Candidates_2026.xlsx")
wb.save(out_path)
print(f"Saved: {out_path}")
print(f"Data rows: {len(rows)} across {len(all_counties)} counties")
