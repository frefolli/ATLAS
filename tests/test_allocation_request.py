"""The request of allocation (X-1): a team asks that clauses of a section of another team be allocated to one of its
own domains. The same fields as a reallocation (with labels of its own), approved by the Design Authority in the same
way."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QMessageBox

from arcadia_tool.model.adr import (adr_defaults, allocation_warnings, approve_reallocation, can_approve,
                                    decided_reallocations, item_primary, principal_of, sections_not_held, type_fields)
from arcadia_tool.model.schema import ADR_ALLOCATION, ADR_SECTION, ADR_TYPE_LABELS, KINDS_BY_NAME, adr_area
from arcadia_tool.ui import srs_trace
from arcadia_tool.ui.element_editor import ElementEditor
from test_adr_team_sections import build


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def request(p, e, items, domain="mine", **values):
    return p.new_element("adr", title="Richiesta", adr_type=ADR_ALLOCATION, status="Proposta", proposer=e["rfi"].uuid,
                         realloc_item=[e[i].uuid for i in items], primary_proposed=e[domain].uuid if domain else None,
                         **values)


def test_the_type_has_the_fields_of_a_reallocation_with_labels_of_its_own(tmp_path):
    assert ADR_ALLOCATION in ADR_TYPE_LABELS and adr_area(ADR_ALLOCATION) == adr_area(ADR_SECTION)
    assert [f.name for f in type_fields(ADR_ALLOCATION)] == [f.name for f in type_fields(ADR_SECTION)]
    p, e = build(tmp_path)
    adr = request(p, e, ["c2"])
    field = KINDS_BY_NAME["adr"].field
    assert field("realloc_item").label_for(adr) == "Clausole richieste"
    assert field("primary_proposed").label_for(adr) == "Dominio richiedente (principale proposto)"
    assert field("realloc_reason").label_for(adr) == "Motivazione della richiesta"
    assert field("realloc_item").label_for(p.new_element("adr", adr_type=ADR_SECTION)) == \
        "Sezioni o clausole da riallocare"
    assert adr_defaults(p.model, ADR_ALLOCATION, e["c2"])["realloc_item"] == [e["c2"].uuid]
    assert item_primary(p.model, adr) == e["theirs"].uuid  # the domain the clause has now


def test_what_does_not_hold_in_a_request(tmp_path):
    p, e = build(tmp_path)
    good = request(p, e, ["c2", "c3"])
    assert allocation_warnings(p.model, good) == [] and sections_not_held(p.model, good) == []  # of another team: fine
    wrong = request(p, e, ["c1", "other"], domain="theirs")
    warnings = " ".join(allocation_warnings(p.model, wrong))
    assert "Il dominio richiedente DF02" in warnings and "non è un dominio del team proponente" in warnings
    assert "3.4.1.5 è già in un dominio del team proponente" in warnings
    assert "3.4.2 non è una clausola" in warnings
    assert allocation_warnings(p.model, p.new_element("adr", adr_type=ADR_SECTION, proposer=e["rfi"].uuid,
                                                      realloc_item=[e["c1"].uuid])) == []


def test_the_design_authority_approves_it_as_a_reallocation(tmp_path):
    p, e = build(tmp_path)
    adr = request(p, e, ["c2"])
    assert can_approve(adr)
    approve_reallocation(p, adr)
    assert e["c2"].get("primary_domain") == e["mine"].uuid and principal_of(p.model, e["c3"]) == e["theirs"].uuid
    assert adr.get("status") == "Decisa" and decided_reallocations(p.model, e["c2"]) == [adr]
    assert item_primary(p.model, adr) == e["theirs"].uuid  # as it was before the approval
    assert srs_trace.received_items(p.model, e["mine"]) == [e["c2"]]


def test_the_sheet(app, tmp_path, monkeypatch):
    p, e = build(tmp_path)
    adr = request(p, e, ["c2"])
    editor = ElementEditor()
    editor.approver = lambda: "Anna"
    editor.edit(p, adr)
    assert editor.field_labels["realloc_item"].text() == "Clausole richieste"
    assert editor.approve_button.text() == "Approva e alloca le clausole"
    assert editor.findChild(QFrame, "sectionsNotHeld") is None  # nothing to say: of another team by its nature
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    editor.approve()
    assert e["c2"].get("primary_domain") == e["mine"].uuid
    wrong = request(p, e, ["c1"], domain="theirs")
    editor = ElementEditor()
    editor.edit(p, wrong)
    frame = editor.findChild(QFrame, "sectionsNotHeld")
    text = " ".join(label.text() for label in frame.findChildren(QLabel))
    assert "RICHIESTA DI ALLOCAZIONE DA VERIFICARE" in text and "già in un dominio del team proponente" in text
    p.close()


def test_the_choice_of_the_clauses_shows_those_of_the_other_teams(app, tmp_path, monkeypatch):
    p, e = build(tmp_path)
    adr = p.new_element("adr", adr_type=ADR_ALLOCATION, status="Proposta", proposer=e["rfi"].uuid)
    asked = []
    monkeypatch.setattr(srs_trace.QMessageBox, "question", lambda *a, **k: asked.append(a) or QMessageBox.No)
    opened = []
    monkeypatch.setattr(srs_trace.TraceAllocationItemsDialog, "exec", lambda self: opened.append(self) or False)
    srs_trace.choose_items(p, adr, "realloc_item", [])
    dialog = opened[0]  # the window of the request, for the same field of a reallocation
    assert dialog.own_box.text() == "Altri team" and dialog.own_box.isChecked()
    assert e["other"].uuid not in dialog.state and e["c2"].uuid in dialog.state  # only clauses can be chosen

    def shown():
        found, it = [], srs_trace.QTreeWidgetItemIterator(dialog.tree)
        while it.value():
            if not it.value().isHidden():
                found.append(p.model.get(it.value().data(0, srs_trace.UUID_ROLE)).get("id"))
            it += 1
        return found
    assert shown() == ["3.4", "3.4.2", "3.4.2.1", "3.4.2.2"]  # 3.4.1.5: of the team already

    def row(item):
        entry = srs_trace.QTreeWidgetItem([item.get("id")])
        entry.setData(0, srs_trace.UUID_ROLE, item.uuid)
        return entry
    dialog.click(row(e["c2"]), srs_trace.PARENT)
    assert dialog.selected == [e["c2"].uuid] and not asked  # of another team: no question
    reallocation = p.new_element("adr", adr_type=ADR_SECTION, status="Proposta", proposer=e["rfi"].uuid)
    monkeypatch.setattr(srs_trace.TraceReallocItemsDialog, "exec", lambda self: opened.append(self) or False)
    srs_trace.choose_items(p, reallocation, "realloc_item", [])
    assert type(opened[-1]) is srs_trace.TraceReallocItemsDialog and opened[-1].own_box.text() == "Propri domini"
    p.close()
