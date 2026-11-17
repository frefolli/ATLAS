"""The title proposed for an ADR: every type has one, from its fields; in the sheet it follows the fields until the team
changes it by hand, and «Proponi titolo» brings it back."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from arcadia_tool.model.adr import proposed_title
from arcadia_tool.model.element import Element
from arcadia_tool.model.schema import (ADR_ALLOCATION, ADR_DELETE_DOMAIN, ADR_DOMAIN_SCOPE, ADR_EXCLUSION, ADR_FUNCTION,
                                       ADR_IMPLEMENTATION, ADR_LOGICAL, ADR_MERGE_DOMAINS, ADR_NEW_DOMAIN, ADR_OTHER,
                                       ADR_OWNER, ADR_PRODUCT_OPTION, ADR_SECTION, ADR_SHARED, ADR_SPLIT_DOMAIN,
                                       ADR_TYPE_LABELS, ADR_UNMAPPED, ADR_WAIVER, SCOPE_CLAUSES, SCOPE_SECTION)
from arcadia_tool.storage.project import Project
from arcadia_tool.ui.element_editor import ElementEditor


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def build(tmp_path):
    p = Project.create(tmp_path / "p", "Prova")
    d1, d2, d3 = (p.new_element("domain", name=n) for n in ("Odometria", "Radio", "Freni"))
    section = p.new_element("requirement", id="3.4.1", item_type="Sezione", primary_domain=d1.uuid)
    c1 = p.new_element("requirement", id="3.4.1.3", item_type="Requisito", parent=section.uuid, text="Uno")
    c2 = p.new_element("requirement", id="3.4.1.5", item_type="Requisito", parent=section.uuid, text="Due")
    sf = p.new_element("system_function", name="Determinare la posizione", domain=d1.uuid)
    ei = p.new_element("exchange_item", name="Posizione treno")
    return p, dict(d1=d1, d2=d2, d3=d3, section=section, c1=c1, c2=c2, sf=sf, ei=ei)


def title(p, **values):
    return proposed_title(p.model, Element("adr", values=values))


def test_every_type_has_a_title_also_with_nothing_written(tmp_path):
    p, _e = build(tmp_path)
    for adr_type in ADR_TYPE_LABELS:
        assert title(p, adr_type=adr_type).strip(), adr_type
    assert title(p) == "Nuova decisione architetturale"


def test_the_title_says_what_the_adr_decides(tmp_path):
    p, e = build(tmp_path)
    d1, d2, d3 = (e[k].get("id") for k in ("d1", "d2", "d3"))
    u = lambda *keys: [e[k].uuid for k in keys]
    assert title(p, adr_type=ADR_NEW_DOMAIN, new_domain_name="Odometria  avanzata",
                 sections_allocated=u("section")) == "Nuovo dominio «Odometria avanzata» per la sezione 3.4.1"
    assert title(p, adr_type=ADR_DELETE_DOMAIN, deleted_domain=e["d3"].uuid) == f"Eliminazione di {d3}"
    assert title(p, adr_type=ADR_MERGE_DOMAINS, merged_domains=u("d1", "d2", "d3"), proposed_domain="Posizione") == \
        f"Fusione di {d1}, {d2} e {d3} in «Posizione»"
    assert title(p, adr_type=ADR_SPLIT_DOMAIN, split_domain=e["d1"].uuid,
                 new_domains=[{"name": "A"}, {"name": "B"}]) == f"Scissione di {d1} in 2 domini"
    assert title(p, adr_type=ADR_DOMAIN_SCOPE, domain=e["d2"].uuid, scope_change="Riduzione") == \
        f"Riduzione dello scopo di {d2}"
    assert title(p, adr_type=ADR_SECTION, realloc_scope=SCOPE_SECTION, realloc_item=u("section"),
                 primary_proposed=e["d2"].uuid) == f"Riallocazione della sezione 3.4.1 da {d1} a {d2}"
    assert title(p, adr_type=ADR_SECTION, realloc_scope=SCOPE_CLAUSES, realloc_item=u("c1", "c2")) == \
        f"Riallocazione delle clausole 3.4.1.3, 3.4.1.5 da {d1}"
    assert title(p, adr_type=ADR_ALLOCATION, realloc_item=u("c1"), primary_proposed=e["d3"].uuid) == \
        f"Richiesta della clausola 3.4.1.3 per {d3}"
    assert title(p, adr_type=ADR_EXCLUSION, excluded_item=u("c2"), excluding_domain=e["d1"].uuid) == \
        f"Esclusione di 3.4.1.5 da {d1}"
    assert title(p, adr_type=ADR_SHARED, shared_items=u("c1"), shared_with=u("d2", "d3")) == \
        f"Condivisione della clausola 3.4.1.3 con {d2} e {d3}"
    assert title(p, adr_type=ADR_UNMAPPED, unmapped_items=u("c1", "c2")) == \
        "Non mappatura delle clausole 3.4.1.3, 3.4.1.5"
    sf = e["sf"].get("id")
    assert title(p, adr_type=ADR_FUNCTION, function=e["sf"].uuid, to_domain=e["d2"].uuid) == \
        f"Spostamento di {sf} da {d1} a {d2}"
    assert title(p, adr_type=ADR_OWNER, exchange_item=e["ei"].uuid).startswith("Proprietà dell'informazione «")
    assert title(p, adr_type=ADR_IMPLEMENTATION, impl_item=e["c1"].uuid) == \
        "Scelta lasciata all'implementazione in 3.4.1.3"
    assert title(p, adr_type=ADR_PRODUCT_OPTION, function=e["sf"].uuid, product_choice="Configurabile") == \
        f"Opzione di prodotto: {sf} (configurabile)"
    assert title(p, adr_type=ADR_LOGICAL, la_operation="Scissione di componente") == "Scissione di componente"
    assert title(p, adr_type=ADR_WAIVER, rule="SA2-07") == "Deroga a SA2-07"
    assert title(p, adr_type=ADR_OTHER, srs_items=u("c1")) == "Decisione trasversale su 3.4.1.3"


def test_in_the_sheet_it_follows_the_fields_until_written_by_hand(app, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    import arcadia_tool.ui.srs_trace as srs_trace

    p, e = build(tmp_path)
    chosen = []
    monkeypatch.setattr(srs_trace, "choose_element", lambda project, element, field, parent=None: chosen.pop(0))

    def pick(name, uuid):  # «Scegli…» of a reference, answered
        chosen.append(uuid)
        editor._pick(editor.draft.schema.field(name))
    d1, d2, d3 = (e[k].get("id") for k in ("d1", "d2", "d3"))
    values = {"adr_type": ADR_SECTION, "status": "Proposta", "realloc_scope": SCOPE_SECTION,
              "realloc_item": [e["section"].uuid]}
    adr = p.new_element("adr", title=title(p, **values), **values)
    assert adr.get("title") == f"Riallocazione della sezione 3.4.1 da {d1}"
    editor = ElementEditor()
    editor.edit(p, adr, editing=True)
    pick("primary_proposed", e["d2"].uuid)  # a field: the title follows it
    assert editor.widgets["title"].text() == f"Riallocazione della sezione 3.4.1 da {d1} a {d2}"
    pick("primary_proposed", e["d3"].uuid)
    assert editor.draft.get("title") == f"Riallocazione della sezione 3.4.1 da {d1} a {d3}"
    editor.widgets["title"].setText("Odometria cede la sezione 3.4.1")  # written by hand: it stays
    editor.flush()
    pick("primary_proposed", e["d2"].uuid)
    assert editor.draft.get("title") == "Odometria cede la sezione 3.4.1"
    editor.propose_title()  # «Proponi titolo»: back to the proposed one, which follows the fields again
    assert editor.widgets["title"].text() == f"Riallocazione della sezione 3.4.1 da {d1} a {d2}"
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    editor.widgets["adr_type"].set_value(ADR_WAIVER)  # another type: its title
    assert editor.widgets["title"].text() == "Deroga a una regola della metodologia"
    editor.widgets["rule"].setText("SA2-07")  # the rule written: the title follows it
    editor.flush()
    assert editor.widgets["title"].text() == "Deroga a SA2-07"
    editor.save_changes()
    assert adr.get("title") == "Deroga a SA2-07"
    decided = p.new_element("adr", title=title(p, **values), **{**values, "status": "Decisa"})
    editor.edit(p, decided, editing=True)  # decided: its title never changes by itself
    pick("primary_proposed", e["d2"].uuid)
    assert editor.draft.get("title") == f"Riallocazione della sezione 3.4.1 da {d1}"
    editor.deleteLater()


def test_a_new_adr_from_the_tree_has_the_title_proposed(app, tmp_path):
    from arcadia_tool.ui import main_window as mw

    p, e = build(tmp_path)
    window = mw.MainWindow()
    window._set_project(p)
    window.tree.create("adr", {"adr_type": ADR_EXCLUSION, "status": "Proposta", "excluded_item": [e["c1"].uuid],
                               "excluding_domain": e["d1"].uuid})
    adr = next(a for a in p.model.of_kind("adr"))
    assert adr.get("title") == f"Esclusione di 3.4.1.3 da {e['d1'].get('id')}"
    window.tree.create("adr", {"adr_type": ADR_WAIVER, "title": "Scritto dal team"})  # a title given: kept
    assert "Scritto dal team" in [a.get("title") for a in p.model.of_kind("adr")]
    window._set_project(None)
    window.close()
