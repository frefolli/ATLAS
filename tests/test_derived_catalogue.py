"""The catalogue of the derived requirements (SA-4): a tab like that of the system functions, opened with a double
click on its group in the model tree, filtered by parent item, system function and functional domain."""
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
    c1 = p.new_element("requirement", id="3.5.1.1", item_type="Requisito", text="Prima")
    c2 = p.new_element("requirement", id="3.6.2.4", item_type="Requisito", text="Seconda")
    f1 = p.new_element("system_function", id="SF-DF01-01", name="Gestire la sessione", domain=radio.uuid)
    f2 = p.new_element("system_function", id="SF-DF02-01", name="Stimare la posizione", domain=odo.uuid)
    d1 = p.new_element("derived_requirement", id="3.5.1.1-D1", name="Apertura", parent=c1.uuid,
                       system_function=f1.uuid, domain=radio.uuid, status="Proposto")
    d2 = p.new_element("derived_requirement", id="3.5.1.1-D2", name="Chiusura", parent=c1.uuid,
                       system_function=f1.uuid)  # its domain: from its function
    d3 = p.new_element("derived_requirement", id="3.6.2.4-D1", name="Posizione", parent=c2.uuid,
                       system_function=f2.uuid, domain=odo.uuid, status="Approvato")
    return p, dict(radio=radio, odo=odo, c1=c1, c2=c2, f1=f1, f2=f2, d1=d1, d2=d2, d3=d3)


def shown(page):
    return [page.table.item(r, 0).text() for r in range(page.table.rowCount()) if not page.table.isRowHidden(r)]


def test_the_catalogue_and_its_filters(app, tmp_path):
    p, e = build(tmp_path)
    page = ElementListPage(p, "derived_requirement")
    headers = [page.table.horizontalHeaderItem(c).text() for c in range(len(page.columns))]
    assert headers == ["ID", "Nome sintetico", "Voce madre", "Funzioni di sistema", "Domini"]  # no status
    assert shown(page) == ["3.5.1.1-D1", "3.5.1.1-D2", "3.6.2.4-D1"] and page.count.text() == "3 requisiti derivati"
    row = [page.table.item(1, c).text() for c in range(len(page.columns))]
    assert row == ["3.5.1.1-D2", "Chiusura", "3.5.1.1", "SF-DF01-01 Gestire la sessione", "DF01 Radio"]
    parent, function, domain = (page.pickers[c] for c in ("parent", "system_function", "domain"))
    assert parent.text() == "Tutte le voci madri" and function.text() == "Tutte le funzioni"
    assert list(domain.labels.values()) == ["DF01 Radio", "DF02 Odometria"]
    assert parent.button.text() == "Voce madre…" and not parent.clear.isVisibleTo(parent)  # buttons, not lists
    # All those of the model, not only those used: a function and an SRS item with no derived requirement too.
    unused = p.new_element("system_function", id="SF-DF02-02", name="Stimare la velocità", domain=e["odo"].uuid)
    free = p.new_element("requirement", id="3.7.1.1", item_type="Requisito", text="Terza")
    page.reload()
    assert unused.uuid in function.labels and parent.labels[free.uuid] == "3.7.1.1"
    # Chosen in the windows of the tool: the SRS items in the traceability window, the functions grouped by
    # domain, the domains, all with search and ticks.
    from arcadia_tool.ui import srs_trace
    seen = []

    def tick_items(dialog):
        seen.append(dialog.findChildren(srs_trace.QLabel)[0].text())
        dialog.set_state(e["c2"].uuid, srs_trace.PARENT)
        return True

    def tick_elements(wanted):
        def run(dialog):
            seen.append(dialog.windowTitle())
            dialog.selected = set(wanted)
            return True
        return run
    original = srs_trace.TraceFilterItemsDialog.exec, srs_trace.TickPickerDialog.exec
    try:
        srs_trace.TraceFilterItemsDialog.exec = tick_items
        parent.open()  # what is chosen, shown after the window is closed
        assert parent.values == [e["c2"].uuid] and shown(page) == ["3.6.2.4-D1"] and parent.text() == "3.6.2.4"
        assert parent.clear.isVisibleTo(parent)
        parent.set_values([])
        srs_trace.TickPickerDialog.exec = tick_elements({e["f1"].uuid})
        function.open()
        assert function.values == [e["f1"].uuid] and shown(page) == ["3.5.1.1-D1", "3.5.1.1-D2"]
        function.set_values([])
        srs_trace.TickPickerDialog.exec = tick_elements({e["odo"].uuid})
        domain.open()
        assert domain.values == [e["odo"].uuid] and shown(page) == ["3.6.2.4-D1"]
        assert domain.text() == "DF02 Odometria"
        domain.clear.click()  # the cross takes the filter away
        assert domain.values == [] and domain.text() == "Tutti i domini" and len(shown(page)) == 3
    finally:
        srs_trace.TraceFilterItemsDialog.exec, srs_trace.TickPickerDialog.exec = original
    assert seen == ["Requisiti derivati · filtro: le voci madri", "Requisiti derivati · filtro: le funzioni di sistema",
                    "Requisiti derivati · filtro: i domini funzionali"]
    parent.set_values([])
    parent.set_values([e["c1"].uuid])
    assert shown(page) == ["3.5.1.1-D1", "3.5.1.1-D2"] and page.count.text() == "2 di 3"
    parent.set_values([])
    function.set_values([e["f2"].uuid])
    assert shown(page) == ["3.6.2.4-D1"]
    function.set_values([])
    domain.set_values([e["radio"].uuid])  # also the one whose domain comes from its function
    assert shown(page) == ["3.5.1.1-D1", "3.5.1.1-D2"]
    parent.set_values([e["c2"].uuid])  # the filters together
    assert shown(page) == []
    domain.set_values([])
    page.search.setText("posizione")  # with the search too
    assert shown(page) == ["3.6.2.4-D1"]
    page.close()
    page.deleteLater()
    p.close()


def test_a_double_click_on_the_group_opens_it_in_a_tab(app, tmp_path):
    from arcadia_tool.ui import main_window as mw

    p, e = build(tmp_path)
    window = mw.MainWindow()
    window._set_project(p)
    group = window.tree._kind_items["derived_requirement"]
    window.tree.tree.itemDoubleClicked.emit(group, 0)
    page = window.pages.currentWidget()
    assert isinstance(page, ElementListPage) and page.kind == "derived_requirement"
    assert window.pages.tabText(window.pages.indexOf(page)) == "Requisiti derivati"
    window._set_project(None)
    window.close()


def test_a_derived_requirement_on_more_system_functions(app, tmp_path, monkeypatch):
    from arcadia_tool.model.links import derived_functions
    from arcadia_tool.ui import srs_trace
    from arcadia_tool.ui.element_editor import ElementEditor

    p, e = build(tmp_path)
    d1 = e["d1"]
    d1.values["system_function"] = e["f1"].uuid  # as written up to 0.12.0: one function, a text
    p.save()
    p.close()
    p = Project.open(p.path)  # read as a list, saved so with the next save
    d1 = p.model.get(d1.uuid)
    assert d1.get("system_function") == [e["f1"].uuid] and d1.uuid in p.pending()
    # Chosen with ticks in its sheet: more functions; its domain stays that of the first one.
    editor = ElementEditor()
    editor.edit(p, d1, editing=True)
    monkeypatch.setattr(srs_trace, "choose_functions", lambda *a, **k: [e["f1"].uuid, e["f2"].uuid])
    editor._choose_system_function()
    listed = editor.widgets["systemFunction"]  # one per row, a double click opens it
    assert [listed.item(i).text() for i in range(listed.count())] == ["SF-DF01-01 Gestire la sessione",
                                                                     "SF-DF02-01 Stimare la posizione"]
    opened = []
    editor.open_requested.connect(opened.append)
    listed.itemDoubleClicked.emit(listed.item(1))
    assert opened == [e["f2"].uuid]
    editor.draft.set("name", "Apertura sessione")
    editor.save_changes()
    assert derived_functions(d1) == [e["f1"].uuid, e["f2"].uuid] and d1.get("domain") == e["radio"].uuid
    # The catalogue shows both, and the filter by function finds it with either.
    page = ElementListPage(p, "derived_requirement")
    row = next(r for r in range(page.table.rowCount()) if page.table.item(r, 0).text() == "3.5.1.1-D1")
    assert page.table.item(row, 3).text() == "SF-DF01-01 Gestire la sessione, SF-DF02-01 Stimare la posizione"
    assert page.table.item(row, 4).text() == "DF01 Radio, DF02 Odometria"  # the domains of its functions
    page.pickers["domain"].set_values([e["odo"].uuid])  # found by either of them
    assert "3.5.1.1-D1" in shown(page)
    page.pickers["domain"].set_values([])
    page.pickers["system_function"].set_values([e["f2"].uuid])
    assert shown(page) == ["3.5.1.1-D1", "3.6.2.4-D1"]
    # Mapped on both: in the lists of both functions.
    assert d1 in srs_trace.derived_of(p.model, e["f1"]) and d1 in srs_trace.derived_of(p.model, e["f2"])
    page.close()
    page.deleteLater()
    p.close()
