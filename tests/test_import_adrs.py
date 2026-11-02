"""«Importa ADR…» of the model tree: the sheets X-1 of the teams in Excel, in any template of the types."""
import openpyxl
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from arcadia_tool.model.schema import ADR_SECTION, ADR_TYPE_LABELS, BOOL, ENUM, MULTIENUM, REF, STR, TABLE, TEXT
from arcadia_tool.storage.adr_sheets import (DUPLICATE, INVALID, NEW, PRESENT, create_adrs, plan_adrs,
                                             read_adr_sheets)
from arcadia_tool.storage.project import Project


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def project(tmp_path):
    p = Project.create(tmp_path / "p", "Prova")
    domains = {n: p.new_element("domain", id=f"DF{n:02d}", name=name) for n, name in
               ((1, "Trackside Information Acquisition"), (2, "Train Position"), (7, "Train Movement Protection"),
                (8, "Mode and Level Management"), (9, "Operational Procedure Execution"))}
    teams = {"T1": p.new_element("team", name="RFI"),
             "T2": p.new_element("team", name="Fondazione Bruno Kessler"),
             "T3": p.new_element("team", name="Università degli Studi di Milano Bicocca",
                                 members=[{"name": "Roberto Crotti", "account": "d" * 32},
                                          {"name": "Luca Guglielmo", "account": "c" * 32}],
                                 referent="Luca Guglielmo"),
             "T4": p.new_element("team", name="INTECS", members=[{"name": "Guido Ioele", "account": "a" * 32},
                                                                 {"name": "Alessandro Tata", "account": "b" * 32}])}
    items = {}
    sequence = iter(range(1, 100))
    chapter = p.new_element("requirement", id="3.14", item_type="Capitolo", sequence=next(sequence))
    for section, clauses in (("3.14.1", ("3.14.1.3", "3.14.1.4")), ("3.15.9", ("3.15.9.4", "3.15.9.5")),
                             ("3.5.3", ("3.5.3.4",)), ("3.5.5", ("3.5.5.1",))):
        s = items[section] = p.new_element("requirement", id=section, item_type="Sezione", parent=chapter.uuid,
                                           sequence=next(sequence))
        for clause in clauses:
            items[clause] = p.new_element("requirement", id=clause, item_type="Requisito", parent=s.uuid,
                                          sequence=next(sequence))
    for letter in "ab":
        items[f"3.15.9.5 {letter})"] = p.new_element("requirement", id=f"3.15.9.5 {letter})", item_type="Voce",
                                                     parent=items["3.15.9.5"].uuid, sequence=next(sequence))
    p.save()
    return p, domains, teams, items


OLD_ROWS = ("ID e titolo", "Tipo di decisione", "Stato", "Superata da", "Proponente (team)", "Data della decisione",
            None, "Dettagli: Riallocazione di sezione o clausola", "Sezione o clausola da riallocare",
            "Dominio principale attuale (sorgente)", "Contributori attuali",
            "Dominio principale proposto\n(destinazione)", "Contributori proposti", "Motivazione della riallocazione")


def old_sheet(path, values, team="Intecs", author="G. Ioele"):
    """A sheet in the template of the first versions, as the teams filled it in."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "X-1"
    ws.append(["X-1 · Decisione architetturale (ADR) · Riallocazione di sezione"])
    ws.append([])
    ws.append(["Template", "X-1", "Team", team, "Versione", "0.1"])
    ws.append(["Autore", author, "Revisore", None, "Data", "30/10/2026"])
    ws.append(["Stato", "Bozza", "Baseline SRS", "SUBSET-026 v3.6.0"])
    ws.append([])
    ws.append(["Identificazione"])
    defaults = {"Superata da": "es. ADR-nnn", "Proponente (team)": "es. T5 · Odometria",
                "Data della decisione": "gg/mm/aaaa", "Stato": "Proposta",
                "Tipo di decisione": "Riallocazione di sezione o clausola",
                "Dominio principale attuale (sorgente)": "Calcolato da ATLAS: il dominio principale della voce",
                "Contributori attuali": "Calcolato da ATLAS: i domini contributori della voce",
                "Contributori proposti": "Uno o più: es. DF07 · Odometria"}
    for label in OLD_ROWS:
        if label is None:
            ws.append([])
        elif label.startswith("Dettagli"):
            ws.append([label])
        else:
            ws.append([label, values.get(label, defaults.get(label))])
    wb.save(path)
    return path


def test_the_sheets_of_the_first_versions_are_imported_with_their_details(tmp_path):
    p, domains, teams, items = project(tmp_path)
    folder = tmp_path / "adr"
    folder.mkdir()
    files = [
        old_sheet(folder / "ADR-005.xlsx", {"ID e titolo": "ADR-005 Spostamento clausola 3.14.1.3 da DF07",
                                            "Sezione o clausola da riallocare": "3.14.1.3",
                                            "Dominio principale proposto\n(destinazione)": "DF08 o DF09",
                                            "Contributori proposti": "DF07 - Train Movement Protection Handling",
                                            "Motivazione della riallocazione": "Le condizioni di trip."}),
        # The ID of the name of the file, the title of another ADR; the team and its author by their abbreviation.
        old_sheet(folder / "ADR-0010.xlsx", {"ID e titolo": "ADR-016 · Spostamento delle clausole di 3.15.9",
                                             "Stato": "Decisa", "Proponente (team)": "Unimib",
                                             "Sezione o clausola da riallocare":
                                                 "Clausole:\n3.15.9.4\n3.15.9.5 a)\n3.15.9.5 b)",
                                             "Dominio principale proposto\n(destinazione)": "DF02 · Train Position",
                                             "Motivazione della riallocazione": "Dati memorizzati a bordo."},
                  team="Unimib", author="Unimib"),
        # A type not foreseen, clauses of two sections, a destination not decided.
        old_sheet(folder / "ADR-022.xlsx", {"ID e titolo": "ADR 22 - Clausole radio",
                                            "Tipo di decisione": "Eliminazione clausola",
                                            "Proponente (team)": "FBK",
                                            "Sezione o clausola da riallocare": "Parte delle clausole 3.5.3.4 e 3.5.5.1",
                                            "Dominio principale proposto\n(destinazione)": "Da definire"},
                  team="Unimib", author="Unimib"),
    ]
    sheets, failed = read_adr_sheets(files)
    assert not failed and len(sheets) == 3
    first, second, third = plan_adrs(p.model, sheets)
    assert [x.ident for x in (first, second, third)] == ["ADR-005", "ADR-010", "ADR-022"]
    assert all(x.outcome == NEW and x.adr_type == ADR_SECTION for x in (first, second, third))
    # ADR-005: the team of the header, the member by initial and surname, the destination of two domains left out.
    assert first.title == "Spostamento clausola 3.14.1.3 da DF07"
    v = first.values
    assert v["status"] == "Proposta" and v["proposer"] == teams["T4"].uuid and v["proposer_member"] == "Guido Ioele"
    assert v["realloc_item"] == [items["3.14.1.3"].uuid] and "primary_proposed" not in v
    assert v["contributors_proposed"] == [domains[7].uuid]  # the name after the ID: no note
    assert any("più domini indicati («DF08 o DF09»)" in w for w in first.warnings)
    assert v["realloc_reason"] == ("Le condizioni di trip.\n\nNote dell'import da ADR-005.xlsx:\n"
                                   "- Dominio principale proposto: DF08 o DF09")
    assert not any(k.startswith("_") or k in ("decision_date", "superseded_by") for k in v)  # the guides: ignored
    # ADR-010: the list items of the project, the team «Unimib», the status of the file not imported.
    v = second.values
    assert v["proposer"] == teams["T3"].uuid  # «Unimib» is the team, not a member: its referent proposes it
    assert v["proposer_member"] == "Luca Guglielmo"
    assert ("Proponente (membro del team)", "Luca Guglielmo (referente del team: il file non indica il membro)")         in second.shown
    assert v["realloc_item"] == [items[i].uuid for i in ("3.15.9.4", "3.15.9.5 a)", "3.15.9.5 b)")]
    assert v["primary_proposed"] == domains[2].uuid and v["status"] == "Proposta"
    assert any("Il titolo riporta ADR-016, il nome del file ADR-010" in w for w in second.warnings)
    assert any("Stato nel file «Decisa»" in w for w in second.warnings)
    assert not any("Proponente (membro" in w for w in second.warnings)
    # ADR-022: the type of the template of the sheet, the rule of one section per reallocation recalled.
    v = third.values
    assert third.title == "Clausole radio" and v["proposer"] == teams["T2"].uuid  # FBK, not the team of the header
    assert "proposer_member" not in v  # no member said, and FBK has no referent
    assert v["realloc_item"] == [items["3.5.3.4"].uuid, items["3.5.5.1"].uuid]
    warnings = " ".join(third.warnings)
    assert "«Eliminazione clausola» non previsto" in warnings and "sezioni diverse (3.5.3, 3.5.5)" in warnings
    assert "«Da definire» non è un dominio del progetto" in warnings
    assert "Parte delle clausole 3.5.3.4 e 3.5.5.1" in v["realloc_reason"]
    assert third.note_field == "realloc_reason" and third.noted


def test_every_template_of_the_types_is_read_back_as_generated(tmp_path):
    """Each type of ADR, filled in, written by «Schede Arcadia» and imported again: the same values."""
    from arcadia_tool.documents.generate import make_doc, write_adrs
    from arcadia_tool.model.adr import common_fields, type_fields

    p, domains, teams, items = project(tmp_path)
    sf = p.new_element("system_function", name="Stimare la velocità", domain=domains[2].uuid)
    ei = p.new_element("exchange_item", name="velocita_stimata")
    lf = p.new_element("logical_function", name="Calcolare la velocità", refines=sf.uuid)
    fc = p.new_element("functional_chain", name="Frenatura di servizio")
    picks = {"domain": [domains[1], domains[2]], "requirement": [items["3.14.1.3"], items["3.14.1.4"]],
             "team": [teams["T3"]], "system_function": [sf], "exchange_item": [ei], "logical_function": [lf],
             "functional_chain": [fc]}

    def sample(f):
        if f.type in (TEXT, STR):
            return f"Testo di {f.name}"
        if f.type == ENUM:
            return f.options[-1]
        if f.type == MULTIENUM:
            return list(f.options[:2])
        if f.type == BOOL:
            return True
        chosen = [items["3.14.1"]] if f.sections_only else next((picks[k] for k in f.ref_kinds if k in picks), [])
        if not chosen:
            return None
        return chosen[0].uuid if f.type == REF else [e.uuid for e in chosen]

    adrs = []
    for n, adr_type in enumerate(ADR_TYPE_LABELS, 1):
        values = {"adr_type": adr_type, "status": "Proposta", "title": f"Decisione {n}",
                  "proposer": teams["T4"].uuid, "proposer_member": "Alessandro Tata"}
        for f in [*type_fields(adr_type), *common_fields(adr_type)]:
            if f.computed or not f.stored or f.by_tool or f.section == "Decisione della DA":
                continue
            if f.type == TABLE:
                row = {}
                for c in f.columns:
                    if c.type == REF:
                        row[c.name] = (teams["T3"] if "team" in c.ref_kinds else sf).uuid
                    elif c.choices == "split_domain_items":
                        row[c.name] = items["3.14.1.3"].uuid
                    else:
                        row[c.name] = c.options[0] if c.options else f"{c.name} 1"
                values[f.name] = [row]
            elif sample(f) not in (None, []):
                values[f.name] = sample(f)
        adrs.append(p.new_element("adr", **values))
    path = write_adrs(make_doc(p, "Prova"), adrs, True, tmp_path / "X-1.xlsx")  # the register, then one per ADR
    written = {a.get("id"): dict(a.values) for a in adrs}
    p.delete_elements([a.uuid for a in adrs])
    sheets, failed = read_adr_sheets([path])
    assert not failed and len(sheets) == len(ADR_TYPE_LABELS) and not any(s.single for s in sheets)
    planned = plan_adrs(p.model, sheets)
    for x in planned:
        assert x.outcome == NEW and not x.warnings, (x.ident, x.warnings)
        expected = {k: v for k, v in written[x.ident].items() if k not in ("id", "decision_date")}
        assert x.values == expected, x.adr_type


def test_an_adr_already_in_the_model_or_twice_in_the_files_is_not_imported(app, tmp_path):
    from arcadia_tool.ui.import_adrs import TICK, ImportAdrsDialog

    p, domains, teams, items = project(tmp_path)
    p.new_element("adr", id="ADR-005", title="Già decisa in ATLAS", adr_type=ADR_SECTION, status="Proposta")
    base = {"Sezione o clausola da riallocare": "3.14.1.4", "Motivazione della riallocazione": "Perché sì."}
    files = [old_sheet(tmp_path / "ADR-005.xlsx", {**base, "ID e titolo": "ADR-005 Doppia"}),
             old_sheet(tmp_path / "ADR-006.xlsx", {**base, "ID e titolo": "ADR-006 Nuova",
                                                   "Superata da": "ADR-007"}),
             old_sheet(tmp_path / "ADR-007.xlsx", {**base, "ID e titolo": "ADR-007 Che la supera"}),
             old_sheet(tmp_path / "copia ADR-007.xlsx", {**base, "ID e titolo": "ADR-007 Copia"}),
             old_sheet(tmp_path / "ADR-008.xlsx", {**base, "Tipo di decisione": "Qualcosa"})]
    wb = openpyxl.Workbook()
    wb.active.append(["Non una scheda ADR"])
    wb.save(tmp_path / "altro.xlsx")
    dialog = ImportAdrsDialog(p, [*files, tmp_path / "altro.xlsx"])
    outcomes = {(x.sheet.path.name, x.written_id): x.outcome for x in dialog.planned}
    assert outcomes[("ADR-005.xlsx", "ADR-005")] == PRESENT and outcomes[("ADR-006.xlsx", "ADR-006")] == NEW
    assert outcomes[("ADR-007.xlsx", "ADR-007")] == NEW and outcomes[("copia ADR-007.xlsx", "ADR-007")] == DUPLICATE
    assert outcomes[("ADR-008.xlsx", "ADR-008")] == NEW  # the type of the template of the sheet
    assert [f[0].name for f in dialog.failed] == ["altro.xlsx"]
    assert "5 ADR nei file · si importano 3" in dialog.counts.text() and "già nel modello: 1" in dialog.counts.text()
    rows = {x.written_id + x.sheet.path.name: row for x, row in dialog.entries}
    assert rows["ADR-005ADR-005.xlsx"].data(TICK, Qt.CheckStateRole) is None  # no tick: not imported
    rows["ADR-008ADR-008.xlsx"].setCheckState(TICK, Qt.Unchecked)
    dialog.import_adrs()
    created = {a.get("id"): a for a in dialog.created}
    assert set(created) == {"ADR-006", "ADR-007"}
    assert created["ADR-006"].get("superseded_by") == created["ADR-007"].uuid  # by the ADR imported with it
    assert p.model.get(created["ADR-006"].uuid) is created["ADR-006"]


def test_an_invalid_sheet_and_the_adr_created_with_an_id_of_atlas(tmp_path):
    p, *_ = project(tmp_path)
    path = old_sheet(tmp_path / "decisione.xlsx", {"ID e titolo": "Una decisione senza numero",
                                                   "Sezione o clausola da riallocare": "3.14.1.3"})
    sheets, _failed = read_adr_sheets([path])
    planned = plan_adrs(p.model, sheets)
    assert planned[0].outcome == NEW and planned[0].ident == ""
    created = create_adrs(p, planned)
    assert created[0].get("id", "").startswith("ADR-") and created[0].get("title") == "Una decisione senza numero"
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in (["X-1 · Decisione architetturale"], ["ID e titolo", "ADR-050 Senza tipo"],
                ["Tipo di decisione", "Qualcosa di nuovo"]):
        ws.append(row)
    wb.save(tmp_path / "ADR-050.xlsx")
    sheets, _failed = read_adr_sheets([tmp_path / "ADR-050.xlsx"])
    invalid = plan_adrs(p.model, sheets)[0]
    assert invalid.outcome == INVALID and not invalid.applicable
    assert "«Qualcosa di nuovo» non riconosciuto" in invalid.warnings[0]


def test_the_menu_of_the_adr_in_the_model_tree_imports(app, tmp_path, monkeypatch):
    from arcadia_tool.ui import import_adrs as ui, model_tree
    from arcadia_tool.ui.main_window import MainWindow

    p, *_ = project(tmp_path)
    path = old_sheet(tmp_path / "ADR-009.xlsx", {"ID e titolo": "ADR-009 Dal menu",
                                                 "Sezione o clausola da riallocare": "3.14.1.3"})
    window = MainWindow()
    window._set_project(p)
    window.show()
    menus = []

    class RecordedMenu(model_tree.QMenu):
        def exec(self, *args):  # not shown: its entries are recorded
            menus.append({a.text(): a for a in self.actions()})
    monkeypatch.setattr(model_tree, "QMenu", RecordedMenu)
    monkeypatch.setattr(ui.QFileDialog, "getOpenFileNames", lambda *a, **k: ([str(path)], ""))
    monkeypatch.setattr(ui.ImportAdrsDialog, "exec", lambda dialog: dialog.import_adrs() or True)
    tree = window.tree
    node = tree._kind_items["adr"]
    parent = node.parent()
    while parent is not None:
        parent.setExpanded(True)
        parent = parent.parent()
    app.processEvents()
    tree._context_menu(tree.tree.visualItemRect(node).center())
    assert "Importa ADR…" in menus[-1]
    menus[-1]["Importa ADR…"].trigger()  # the choice of the files, then the summary
    created = [a for a in p.model.of_kind("adr") if a.get("id") == "ADR-009"]
    assert created and created[0].uuid in tree._items
    assert "1 ADR create" in window.statusBar().currentMessage()
    window.save()
    assert not p.pending()
    window._set_project(None)
    window.close()


def test_at_the_end_of_the_import_a_report_can_be_saved(app, tmp_path, monkeypatch):
    from arcadia_tool.ui import import_adrs as ui

    p, domains, teams, items = project(tmp_path)
    p.new_element("adr", id="ADR-006", title="Già in ATLAS", adr_type=ADR_SECTION, status="Proposta")
    files = [old_sheet(tmp_path / "ADR-005.xlsx", {"ID e titolo": "ADR-005 Spostamento",
                                                   "Sezione o clausola da riallocare": "3.14.1.3",
                                                   "Dominio principale proposto\n(destinazione)": "DF08 o DF09"}),
             old_sheet(tmp_path / "ADR-006.xlsx", {"ID e titolo": "ADR-006 Doppia"}),
             old_sheet(tmp_path / "ADR-007.xlsx", {"ID e titolo": "ADR-007 Lasciata fuori"}, team="Unimib",
                       author="Unimib")]
    report = tmp_path / "report.xlsx"
    asked = []
    monkeypatch.setattr(ui.QFileDialog, "getOpenFileNames", lambda *a, **k: ([str(f) for f in files], ""))
    monkeypatch.setattr(ui.QMessageBox, "question", lambda *a, **k: asked.append(a[2]) or ui.QMessageBox.Yes)
    monkeypatch.setattr(ui.QFileDialog, "getSaveFileName", lambda *a, **k: (str(report), ""))

    def run(dialog):  # ADR-007 left out in the summary
        row = next(r for x, r in dialog.entries if x.written_id == "ADR-007")
        row.setCheckState(ui.TICK, ui.Qt.Unchecked)
        dialog.import_adrs()
        return True
    monkeypatch.setattr(ui.ImportAdrsDialog, "exec", run)
    created = ui.import_adrs(p, author="Anna Bianchi")
    assert [a.get("id") for a in created] == ["ADR-005"]
    assert "Import completato: 1 ADR creata" in asked[-1] and "Salvare un report" in asked[-1]
    book = openpyxl.load_workbook(report)
    assert book.sheetnames == ["Riepilogo", "ADR", "Dettaglio"]
    summary = {r[0]: r[1] for r in book["Riepilogo"].iter_rows(min_row=4, values_only=True) if r[0]}
    assert summary["ADR nei file"] == 3 and summary["Importata"] == 1
    assert summary["Già nel modello: non importata"] == 1 and summary["Esclusa nell'anteprima"] == 1
    adrs = {r[2]: r for r in book["ADR"].iter_rows(min_row=2, values_only=True)}
    assert adrs["ADR-005"][3] == "ADR-005" and adrs["ADR-005"][8] == "Importata" and adrs["ADR-005"][9] == 1
    assert adrs["ADR-006"][8] == "Già nel modello: non importata"
    assert adrs["ADR-007"][6] == "T3 Università degli Studi di Milano Bicocca"
    detail = [r for r in book["Dettaglio"].iter_rows(min_row=2, values_only=True) if r[0] == "ADR-005"]
    kinds = {r[2] for r in detail}
    assert kinds == {"Importato", "Scelta", "Avviso"}
    texts = [r[3] for r in detail]
    assert "ID ADR-005: dal nome del file ADR-005.xlsx" in texts
    assert "Proponente (membro del team) Guido Ioele: dall'autore della scheda («G. Ioele»)" in texts
    assert any("Stato «Proposta»: sempre" in t for t in texts)
    warning = next(r for r in detail if r[2] == "Avviso")
    assert "più domini indicati" in warning[3] and warning[4] == "Riportato in «Motivazione della riallocazione»"
    later = [r[3] for r in book["Dettaglio"].iter_rows(min_row=2, values_only=True) if r[0] == "ADR-007"]
    assert any("il referente del team" in t for t in later)
    # Not wanted: nothing is written.
    report.unlink()
    monkeypatch.setattr(ui.QMessageBox, "question", lambda *a, **k: ui.QMessageBox.No)
    p2, *_ = project(tmp_path / "secondo")
    ui.import_adrs(p2)
    assert not report.exists()
