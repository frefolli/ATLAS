"""The choice of the clauses shared or mapped to no domain: only clauses (four numbers or more), not sections; «Propri
domini», ticked at first, shows only those of the domains of the team proposing the ADR."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from arcadia_tool.model.schema import ADR_SHARED, ADR_UNMAPPED
from arcadia_tool.storage.project import Project
from arcadia_tool.ui import srs_trace


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def build(tmp_path):
    p = Project.create(tmp_path / "p", "Prova")
    rfi, fbk = p.new_element("team", name="RFI"), p.new_element("team", name="FBK")
    mine = p.new_element("domain", name="Mio", team=rfi.uuid)
    theirs = p.new_element("domain", name="Loro", team=fbk.uuid)
    chapter = p.new_element("requirement", id="3.8", item_type="Capitolo")
    own = p.new_element("requirement", id="3.8.2", item_type="Sezione", parent=chapter.uuid, primary_domain=mine.uuid)
    other = p.new_element("requirement", id="3.8.4", item_type="Sezione", parent=chapter.uuid,
                          primary_domain=theirs.uuid)
    c1 = p.new_element("requirement", id="3.8.2.1", item_type="Requisito", parent=own.uuid, sequence=1)
    c2 = p.new_element("requirement", id="3.8.4.1", item_type="Requisito", parent=other.uuid, sequence=1)
    c3 = p.new_element("requirement", id="3.8.4.2", item_type="Requisito", parent=other.uuid, sequence=2,
                       contributing_domains=[mine.uuid])  # the team contributes to it
    return p, dict(rfi=rfi, own=own, other=other, c1=c1, c2=c2, c3=c3)


def shown(dialog, p):
    found, it = [], srs_trace.QTreeWidgetItemIterator(dialog.tree)
    while it.value():
        if not it.value().isHidden():
            found.append(p.model.get(it.value().data(0, srs_trace.UUID_ROLE)).get("id"))
        it += 1
    return found


@pytest.mark.parametrize("adr_type,field", [(ADR_SHARED, "shared_items"), (ADR_UNMAPPED, "unmapped_items")])
def test_only_clauses_and_those_of_the_team_at_first(app, tmp_path, monkeypatch, adr_type, field):
    p, e = build(tmp_path)
    adr = p.new_element("adr", adr_type=adr_type, status="Proposta", proposer=e["rfi"].uuid)
    opened = []
    monkeypatch.setattr(srs_trace.TraceClausesDialog, "exec", lambda self: opened.append(self) or False)
    srs_trace.choose_items(p, adr, field, [])
    dialog = opened[0]
    assert e["own"].uuid not in dialog.state and e["other"].uuid not in dialog.state  # sections: not to choose
    assert {e["c1"].uuid, e["c2"].uuid, e["c3"].uuid} <= set(dialog.state)
    assert "non le sezioni (es. 3.8.2)" in dialog.findChildren(srs_trace.QLabel)[1].text()  # the hint on top
    box = dialog.own_box
    assert box.text() == "Propri domini" and box.isChecked()
    assert shown(dialog, p) == ["3.8", "3.8.2", "3.8.2.1", "3.8.4", "3.8.4.2"]  # 3.8.4.1: of the other team
    box.setChecked(False)  # all the clauses
    assert shown(dialog, p) == ["3.8", "3.8.2", "3.8.2.1", "3.8.4", "3.8.4.1", "3.8.4.2"]
    p.close()


def test_a_clause_already_chosen_of_another_team_stays_shown(app, tmp_path):
    p, e = build(tmp_path)
    adr = p.new_element("adr", adr_type=ADR_SHARED, status="Proposta", proposer=e["rfi"].uuid,
                        shared_items=[e["c2"].uuid])
    dialog = srs_trace.TraceClausesDialog(p, adr.copy(), "shared_items")
    assert "3.8.4.1" in shown(dialog, p) and dialog.selected == [e["c2"].uuid]
    p.close()
