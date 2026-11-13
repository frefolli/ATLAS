"""The view of the traceability register (SA-3): a tab like the catalogues of the functions and of the derived
requirements, opened with a double click on its group in the model tree, filtered by SRS item, function (primary or
secondary), principal domain of the item and outcome."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from arcadia_tool.storage.project import Project
from arcadia_tool.ui.element_list import ElementListPage


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def build(tmp_path):
    p = Project.create(tmp_path / "p", "Prova")
    radio = p.new_element("domain", id="DF01", name="Radio")
    odo = p.new_element("domain", id="DF02", name="Odometria")
    s1 = p.new_element("requirement", id="3.5.1", item_type="Sezione", primary_domain=radio.uuid)
    s2 = p.new_element("requirement", id="3.6.2", item_type="Sezione", primary_domain=odo.uuid)
    c1 = p.new_element("requirement", id="3.5.1.1", item_type="Requisito", parent=s1.uuid, category=["Bordo"])
    c2 = p.new_element("requirement", id="3.6.2.4", item_type="Requisito", parent=s2.uuid, category=["Bordo"])
    c3 = p.new_element("requirement", id="3.6.2.10", item_type="Requisito", parent=s2.uuid, category=["Definizione"])
    f1 = p.new_element("system_function", id="SF-DF01-01", name="Gestire la sessione", domain=radio.uuid)
    f2 = p.new_element("system_function", id="SF-DF02-01", name="Stimare la posizione", domain=odo.uuid)
    r1 = p.new_element("trace_record", requirement=c1.uuid, primary_functions=[f1.uuid],
                       outcome="Tracciata a funzione", status="Proposto", notes="Sessione radio")
    r2 = p.new_element("trace_record", requirement=c2.uuid, primary_functions=[f2.uuid],
                       secondary_functions=[f1.uuid], outcome="Tracciata a funzione", status="Approvato")
    r3 = p.new_element("trace_record", requirement=c3.uuid, outcome="Non tracciata", status="Da analizzare")
    return p, dict(radio=radio, odo=odo, c1=c1, c2=c2, c3=c3, f1=f1, f2=f2, r1=r1, r2=r2, r3=r3)


def shown(page):
    return [page.table.item(r, 0).text() for r in range(page.table.rowCount()) if not page.table.isRowHidden(r)]


def test_the_register_and_its_filters(app, tmp_path, monkeypatch):
    from arcadia_tool.ui import element_editor, srs_trace

    p, e = build(tmp_path)
    page = ElementListPage(p, "trace_record")
    headers = [page.table.horizontalHeaderItem(c).text() for c in range(len(page.columns))]
    assert headers == ["Voce SRS", "Categoria cap. 9", "Funzioni di sistema", "Esito", "Dominio principale"]
    assert shown(page) == ["3.5.1.1", "3.6.2.4", "3.6.2.10"]  # by the number of the item
    row = [page.table.item(1, c).text() for c in range(len(page.columns))]
    # All the functions traced to the item: primary and secondary of its record, by ID.
    assert row == ["3.6.2.4", "Bordo", "SF-DF01-01 Gestire la sessione, SF-DF02-01 Stimare la posizione",
                   "Tracciata a funzione", "DF02 Odometria"]
    assert page.count.text() == "3 esiti"
    item, function, domain, outcome = (page.pickers[c] for c in ("requirement", "functions", "domain", "outcome"))
    assert [p_.button.text() for p_ in (item, function, domain, outcome)] == [
        "Voce SRS…", "Funzioni di sistema…", "Dominio principale…", "Esito…"]
    function.set_values([e["f1"].uuid])  # primary or secondary
    assert shown(page) == ["3.5.1.1", "3.6.2.4"] and page.count.text() == "2 di 3"
    function.set_values([])
    domain.set_values([e["odo"].uuid])  # the principal domain of the item (from its section)
    assert shown(page) == ["3.6.2.4", "3.6.2.10"]
    # The outcomes: chosen with ticks in a window.
    seen = []

    def tick(dialog):
        seen.append(dialog.windowTitle())
        for i in range(dialog.list.count()):
            x = dialog.list.item(i)
            x.setCheckState(Qt.Checked if x.data(Qt.UserRole) == "Non tracciata" else Qt.Unchecked)
        return True
    monkeypatch.setattr(element_editor.RefPicker, "exec", tick)
    outcome.open()
    assert seen == ["Registro di tracciabilità · filtro: gli esiti"]
    assert outcome.values == ["Non tracciata"] and shown(page) == ["3.6.2.10"]
    assert outcome.text() == "Non tracciata"
    domain.set_values([])
    outcome.set_values([])
    # The SRS items: in the traceability window.
    monkeypatch.setattr(srs_trace.TraceFilterItemsDialog, "exec",
                        lambda d: d.set_state(e["c1"].uuid, srs_trace.PARENT) or True)
    item.open()
    assert shown(page) == ["3.5.1.1"] and item.text() == "3.5.1.1"
    page.close()
    page.deleteLater()
    p.close()


def test_a_double_click_on_the_group_opens_it_in_a_tab(app, tmp_path):
    from arcadia_tool.ui import main_window as mw

    p, e = build(tmp_path)
    window = mw.MainWindow()
    window._set_project(p)
    window.tree.tree.itemDoubleClicked.emit(window.tree._kind_items["trace_record"], 0)
    page = window.pages.currentWidget()
    assert isinstance(page, ElementListPage) and page.kind == "trace_record"
    assert window.pages.tabText(window.pages.indexOf(page)) == "Registro di tracciabilità"
    window._set_project(None)
    window.close()


def test_a_clause_decomposed_takes_its_functions_from_its_derived_requirements(app, tmp_path):
    from arcadia_tool.model.links import record_functions, record_summary
    from arcadia_tool.ui.element_editor import ElementEditor

    p, e = build(tmp_path)
    r3 = e["r3"]
    r3.set("outcome", "Scomposta in requisiti derivati")
    r3.set("primary_functions", [e["f2"].uuid])  # written by hand before: no longer what counts
    d1 = p.new_element("derived_requirement", id="3.6.2.10-D1", parent=e["c3"].uuid,
                       system_function=[e["f1"].uuid, e["f2"].uuid])
    d2 = p.new_element("derived_requirement", id="3.6.2.10-D2", parent=e["c3"].uuid)  # not mapped yet
    assert record_functions(p.model, r3) == ([], [e["f1"].uuid, e["f2"].uuid])
    assert record_summary(p.model, r3).startswith("1 derivati su 2 mappati")
    d2.set("system_function", [e["f1"].uuid])  # both on SF-DF01-01: it is the primary function
    assert record_functions(p.model, r3) == ([e["f1"].uuid], [e["f2"].uuid])
    assert record_summary(p.model, r3) == "Dai 2 derivati della voce"
    # The register shows them, marked; the filter by function finds the clause through its derived requirements.
    page = ElementListPage(p, "trace_record")
    row = shown(page).index("3.6.2.10")
    assert page.table.item(row, 2).text() == "SF-DF01-01 Gestire la sessione, SF-DF02-01 Stimare la posizione"
    page.pickers["functions"].set_values([e["f2"].uuid])
    assert "3.6.2.10" in shown(page)
    # The sheet: the functions read-only, from the derived requirements.
    editor = ElementEditor()
    editor.edit(p, r3, editing=True)
    primary = editor.widgets["primary_functions"]
    assert primary.value() == [e["f1"].uuid] and not primary.findChildren(type(editor.save_button))[0].isVisible()
    assert "Calcolate dai requisiti derivati" in primary.list.toolTip()
    page.close()
    page.deleteLater()
    del d1
    p.close()


def test_the_functions_traced_to_a_clause_come_from_every_source(tmp_path):
    from arcadia_tool.model.links import traced_functions

    p, e = build(tmp_path)
    bullet = p.new_element("requirement", id="3.5.1.1 a)", item_type="Voce", parent=e["c1"].uuid)
    f3 = p.new_element("system_function", id="SF-DF02-02", name="Stimare la velocità", domain=e["odo"].uuid,
                       sections=[bullet.uuid])  # allocated to a list item of the clause (SA-2)
    f4 = p.new_element("system_function", id="SF-DF02-03", name="Stimare l'accelerazione", domain=e["odo"].uuid)
    p.new_element("derived_requirement", id="3.5.1.1-D1", parent=e["c1"].uuid, system_function=[f4.uuid])
    logical = p.new_element("logical_function", name="Calcolare")
    e["r1"].set("secondary_functions", [logical.uuid])  # a logical function: not a system function
    assert traced_functions(p.model, e["c1"].uuid) == [e["f1"].uuid, f3.uuid, f4.uuid]
    assert traced_functions(p.model, e["c3"].uuid) == []
    p.close()
