"""The report of an import of ADR (see ui.import_adrs) as an Excel file: a summary sheet, then the ADR of the files
one per row (imported or not, and why), then the detail of each: the fields imported, the choices the import made
(the ID, the type, the proposer…) and the warnings, with what was kept in the notes of the motivation."""
from collections import Counter
from datetime import date

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.table import Table, TableStyleInfo

from arcadia_tool.model.schema import KINDS_BY_NAME
from arcadia_tool.storage.adr_sheets import DUPLICATE, INVALID, NEW, PRESENT

DARK, LIGHT, LINE, MUTED = "1F3A5F", "EEF3F9", "C9D1DC", "6B7280"
GREEN, AMBER, RED = "166534", "92400E", "B42318"
IMPORTED, LEFT_OUT = "Importata", "Esclusa nell'anteprima"
OUTCOMES = {PRESENT: "Già nel modello: non importata", DUPLICATE: "Ripetuta in un altro file: non importata",
            INVALID: "Tipo non riconosciuto: non importata"}
COLOURS = {IMPORTED: GREEN, LEFT_OUT: MUTED}
ADR_COLUMNS = (("File", 18), ("Foglio", 10), ("ID nel file", 12), ("ID nel modello", 14), ("Titolo", 50),
               ("Tipo di decisione", 30), ("Proponente (team)", 30), ("Proponente (membro)", 22), ("Esito", 30),
               ("Avvisi", 9))
DETAIL_COLUMNS = (("ID", 12), ("File", 18), ("Cosa", 14), ("Campo o scelta", 90), ("Note della motivazione", 26))
WHAT = (("Importato", GREEN), ("Scelta", "1F3A5F"), ("Avviso", AMBER))


def outcome(p, imported):
    """What became of a planned ADR. imported: {planned ADR (id) → ADR created}."""
    if id(p) in imported:
        return IMPORTED
    if p.outcome == NEW:
        return LEFT_OUT
    return OUTCOMES.get(p.outcome, p.outcome)


def _style(sheet, columns, border):
    for c, (label, width) in enumerate(columns, start=1):
        cell = sheet.cell(row=1, column=c, value=label)
        cell.font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor=DARK)
        cell.alignment = Alignment(vertical="center", wrap_text=True)
        cell.border = border
        sheet.column_dimensions[cell.column_letter].width = width


def _rows(sheet, rows, border, colours=None, wrap=()):
    for r, values in enumerate(rows, start=2):
        for c, value in enumerate(values, start=1):
            cell = sheet.cell(row=r, column=c, value=value)
            colour = colours(values, c) if colours else None
            cell.font = Font(name="Arial", size=10, bold=c == 1, color=colour)
            cell.alignment = Alignment(vertical="top", wrap_text=c in wrap)
            cell.border = border
            if c == 1:
                cell.fill = PatternFill("solid", fgColor=LIGHT)


def _table(sheet, name, columns, count):
    if count:
        last = sheet.cell(row=1, column=len(columns)).column_letter
        table = Table(displayName=name, ref=f"A1:{last}{1 + count}")
        table.tableStyleInfo = TableStyleInfo(name="TableStyleLight1", showRowStripes=False)
        sheet.add_table(table)
    sheet.freeze_panes = "B2"


def write_adr_import_report(model, planned, created, failed, path, project_name="", author="", today=None):
    """Write the report. planned: the ADR of the files (see storage.adr_sheets.plan_adrs); created: {id(planned
    ADR) → ADR created}; failed: [(path, why)] the files not read."""
    today = today or date.today()
    kind = KINDS_BY_NAME["adr"]
    side = Side(style="thin", color=LINE)
    border = Border(left=side, right=side, top=side, bottom=side)
    book = Workbook()
    ws = book.active
    ws.title = "Riepilogo"
    ws["A1"] = "Import delle ADR"
    ws["A1"].font = Font(name="Arial", size=14, bold=True)
    ws["A2"] = " · ".join(t for t in (f"Progetto {project_name}" if project_name else "",
                                      f"Importate da {author}" if author else "",
                                      f"il {today:%d/%m/%Y}") if t)
    ws["A2"].font = Font(name="Arial", size=9, color=MUTED)
    outcomes = Counter(outcome(p, created) for p in planned)
    files = {p.sheet.path.name for p in planned} | {path_.name for path_, _why in failed}
    summary = [("File letti", len(files) - len(failed)), ("File non letti", len(failed)),
               ("ADR nei file", len(planned)), *((o, n) for o, n in outcomes.most_common()),
               ("ADR importate con avvisi", sum(1 for p in planned if id(p) in created and p.warnings))]
    for r, (label, value) in enumerate(summary, start=4):
        ws.cell(row=r, column=1, value=label).font = Font(name="Arial", size=10, bold=True)
        cell = ws.cell(row=r, column=2, value=value)
        cell.font = Font(name="Arial", size=10, color=COLOURS.get(label))
        for c in (1, 2):
            ws.cell(row=r, column=c).border = border
    ws.column_dimensions["A"].width = 40
    ws.column_dimensions["B"].width = 14
    if failed:
        start = len(summary) + 6
        ws.cell(row=start, column=1, value="File non letti").font = Font(name="Arial", size=11, bold=True)
        for r, (path_, why) in enumerate(failed, start=start + 1):
            ws.cell(row=r, column=1, value=path_.name).font = Font(name="Arial", size=10)
            ws.cell(row=r, column=2, value=why).font = Font(name="Arial", size=10, color=RED)

    sheet = book.create_sheet("ADR")
    _style(sheet, ADR_COLUMNS, border)
    rows = []
    for p in planned:
        adr = created.get(id(p))
        team = model.get(p.values.get("proposer")) if p.values.get("proposer") else None
        rows.append((p.sheet.path.name, p.sheet.sheet if not p.sheet.single else "", p.written_id,
                     (adr.get("id") if adr is not None else (p.existing.get("id") if p.existing else "")),
                     p.title, p.adr_type or "", model.label(team) if team is not None else "",
                     p.values.get("proposer_member") or "", outcome(p, created), len(p.warnings)))
    outcome_column = len(ADR_COLUMNS) - 1

    def colour(values, c):
        if c == outcome_column:
            return COLOURS.get(values[c - 1], RED)
        if c == outcome_column + 1 and values[c - 1]:
            return AMBER
        return None
    _rows(sheet, rows, border, colour, wrap=(5,))
    _table(sheet, "ADR_importate", ADR_COLUMNS, len(rows))

    detail = book.create_sheet("Dettaglio")
    _style(detail, DETAIL_COLUMNS, border)
    rows = []
    for p in planned:
        adr = created.get(id(p))
        ident = adr.get("id") if adr is not None else p.written_id
        kept = kind.field(p.note_field).label if p.note_field else ""
        for label, text in p.shown:
            rows.append((ident, p.sheet.path.name, "Importato", f"{label}: {text}", ""))
        for choice in p.choices:
            rows.append((ident, p.sheet.path.name, "Scelta", choice, ""))
        for warning in p.warnings:
            noted = kept if kept and warning in p.noted else ""
            rows.append((ident, p.sheet.path.name, "Avviso", warning, f"Riportato in «{noted}»" if noted else ""))
    colours = dict(WHAT)
    _rows(detail, rows, border, lambda values, c: colours.get(values[2]) if c == 3 else None, wrap=(4,))
    _table(detail, "ADR_dettaglio", DETAIL_COLUMNS, len(rows))
    book.properties.title = f"Import delle ADR · {project_name}"
    book.save(path)
    return path
