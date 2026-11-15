"""The interfaces between the domains (SA-5): the N² matrix, the context of a domain, the state of the exchanges on
the arrows (agreed, to agree, datum to define). Generated from the model, never stored."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from arcadia_tool.model import diagrams as dg
from arcadia_tool.model.interfaces import UNDEFINED, interface_matrix, summary
from arcadia_tool.model.schema import DIAGRAM_DATAFLOW
from test_diagrams import build, view


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def agree(p, fe):
    fe.set("status", "Concordato")
    p.update(fe)


def test_the_matrix_of_the_interfaces(tmp_path):
    p, d, f, x, chain, rbc, alone = build(tmp_path)
    agree(p, x["brake"])
    inside = p.new_element("functional_exchange", id="FE-DF06-DF06-01", source=f[(6, 4)].uuid,
                           target=f[(6, 6)].uuid)  # inside DF06, without a datum
    loose = p.new_element("functional_exchange", source=alone.uuid, target=f[(6, 4)].uuid)  # a function without domain
    m = interface_matrix(p.model)
    # Every domain (also one without exchanges), then the actors that exchange something.
    assert [e.get("id") for e in m.ends] == ["DF02", "DF05", "DF06", "DF11", "OE-01"]
    assert [fe.get("id") for fe in m.cell(d[6].uuid, d[11].uuid).exchanges] == ["FE-DF06-DF11-01"]
    assert m.cell(d[11].uuid, d[6].uuid).count == 1 and m.cell(d[6].uuid, d[2].uuid) is None
    assert m.cell(rbc.uuid, d[5].uuid).count == 1
    assert m.cell(d[6].uuid, d[6].uuid).exchanges == [inside]  # on the diagonal
    assert m.without_domain == 1 and loose.uuid not in {fe.uuid for c in m.cells.values() for fe in c.exchanges}
    # Interfaces between two different ends, exchanges, to agree, without a datum.
    assert summary(m) == (5, 6, 5, 1)


def test_the_matrix_page(app, tmp_path):
    from arcadia_tool.ui.interfaces import AGREED_BG, INSIDE_BG, OPEN_BG, InterfacesPage
    p, d, f, x, chain, rbc, alone = build(tmp_path)
    agree(p, x["brake"])
    page = InterfacesPage(p)
    t = page.table
    assert t.rowCount() == t.columnCount() == 5
    assert [t.verticalHeaderItem(i).text() for i in range(5)] == ["DF02", "DF05", "DF06", "DF11", "OE-01"]
    agreed_cell, open_cell = t.item(2, 3), t.item(3, 2)  # DF06 → DF11 agreed; DF11 → DF06 to agree
    assert agreed_cell.text() == "EI-Comando dei freni" and agreed_cell.background().color().name() == AGREED_BG.lower()
    assert open_cell.background().color().name() == OPEN_BG.lower()
    assert "FE-DF11-DF06-01" in open_cell.toolTip() and "senza stato" in open_cell.toolTip()
    assert t.item(2, 2).background().color().name() == INSIDE_BG.lower()
    assert "5 interfacce · 5 scambi · 4 da concordare" in page.counts.text()
    opened, contexts = [], []
    page.open_requested.connect(opened.append)
    page.context_requested.connect(contexts.append)
    page._cell_opened(2, 3)
    page._end_opened(2)
    page._end_opened(4)  # an actor: no context
    assert opened == [x["brake"].uuid] and contexts == [d[6].uuid]
    # The model changes: drawn again.
    agree(p, x["inputs"])
    page.refresh()
    assert page.table.item(3, 2).background().color().name() == AGREED_BG.lower()


def test_the_context_of_a_domain(tmp_path):
    p, d, f, x, chain, rbc, alone = build(tmp_path)
    v = dg.context_view(p.model, d[6])
    assert v.get("name") == "Contesto di DF06 Dominio 6" and p.model.get(v.uuid) is None  # not in the model
    keys = set(dg.positions(v))
    assert {f[(6, 4)].uuid, f[(6, 6)].uuid, d[2].uuid, d[5].uuid, d[11].uuid} == keys
    df = dg.dataflow(p.model, v)
    # Only the exchanges of DF06 (not RBC → DF05, which is not in the view anyway).
    assert sorted(x_.ident for e in df.edges for x_ in e.exchanges) == [
        "FE-DF02-DF06-01", "FE-DF05-DF06-01", "FE-DF06-DF11-01", "FE-DF11-DF06-01"]
    placed = dg.positions(v)
    # What sends to it on the left, the domain in the middle, what only receives on the right (none: DF11 sends too).
    assert placed[d[2].uuid][0] == 0 and placed[d[5].uuid][0] == 0
    assert placed[f[(6, 4)].uuid][0] > placed[d[2].uuid][0]
    # A domain with exchanges between two neighbours: not shown.
    df5 = dg.dataflow(p.model, dg.context_view(p.model, d[5]))
    assert {(e.source, e.target) for e in df5.edges} == {(rbc.uuid, f[(5, 1)].uuid), (f[(5, 1)].uuid, d[6].uuid)}


def test_the_arrows_say_what_is_to_agree_and_to_define(app, tmp_path):
    from arcadia_tool.ui.diagrams import ARROW, OPEN, DiagramPage
    p, d, f, x, chain, rbc, alone = build(tmp_path)
    agree(p, x["brake"])
    x["inputs"].set("exchange_item", None)
    p.update(x["inputs"])
    v = view(p, DIAGRAM_DATAFLOW, [d[6].uuid, d[11].uuid])
    page = DiagramPage(p, v)
    arrows = {a.key: a for a in page.arrows}
    assert arrows[x["brake"].uuid].color == ARROW and arrows[x["brake"].uuid].lines == [
        "EI-Comando dei freni", "FE-DF06-DF11-01"]
    assert arrows[x["inputs"].uuid].color == OPEN
    assert arrows[x["inputs"].uuid].lines == [UNDEFINED, "FE-DF11-DF06-01 · da concordare"]
    assert not page.legend.isHidden()


def test_the_window_opens_the_generated_views(app, tmp_path):
    from arcadia_tool.ui import main_window as mw
    from arcadia_tool.ui.diagrams import DiagramPage
    from arcadia_tool.ui.interfaces import InterfacesPage
    p, d, f, x, chain, rbc, alone = build(tmp_path)
    window = mw.MainWindow()
    window._set_project(p)
    window.tree.breakdown_requested.emit(dg.INTERFACES)
    assert isinstance(window.pages.currentWidget(), InterfacesPage)
    window.pages.currentWidget().context_requested.emit(d[6].uuid)
    page = window.pages.currentWidget()
    assert isinstance(page, DiagramPage) and page.generated is not None and not page.save_button.isVisibleTo(page)
    assert not page.side_tabs.isTabVisible(1)  # its elements are given
    # A new exchange of DF06 with DF02: the context follows the model.
    new = p.new_element("functional_exchange", source=f[(6, 6)].uuid, target=f[(2, 1)].uuid)
    window._model_changed()
    assert any(a.key == new.uuid for a in page.arrows) and not page.dirty
    # The domain deleted: its context closed.
    p.delete_element(d[6].uuid)
    window._model_changed()
    assert dg.CONTEXT + d[6].uuid not in window.diagram_pages
    window._set_project(None)
    window.close()
