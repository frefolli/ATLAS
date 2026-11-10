"""System Requirements Specifications: the clauses the teams declare shared among domains or mapped to no domain, each
with an ADR filled by the tool; their lists in the tree, their catalogue, the approval of the Design Authority."""
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication

from arcadia_tool.model.adr import (APPROVED, approve_sharing, approve_unmapped, clause_decisions, impacted_domains,
                                    outcome, related_adrs, shared_contributors, shared_derived, shared_primary,
                                    unmapped_by_decision, unmapped_section_domains, unmapped_sections)
from arcadia_tool.model.schema import ADR_SHARED, ADR_UNMAPPED
from arcadia_tool.storage.project import Project


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def project(tmp_path):
    p = Project.create(tmp_path / "p", "Prova")
    team = p.new_element("team", name="FBK", members=[{"name": "Mario Rossi", "account": "b" * 32}])
    other = p.new_element("team", name="RFI")
    d1 = p.new_element("domain", name="Odometria", team=other.uuid)
    d2 = p.new_element("domain", name="Radio", team=team.uuid)
    d3 = p.new_element("domain", name="Frenatura", team=other.uuid)
    section = p.new_element("requirement", id="3.5.3", title="Sezione", item_type="Sezione", primary_domain=d1.uuid,
                            contributing_domains=[d3.uuid])
    clause = p.new_element("requirement", id="3.5.3.7", text="La clausola", item_type="Requisito",
                           parent=section.uuid, category=["Bordo"])
    ground = p.new_element("requirement", id="3.5.3.8", text="Di terra", item_type="Requisito", parent=section.uuid,
                           category=["Terra"])
    derived = p.new_element("derived_requirement", id="3.5.3.7-D1", parent=clause.uuid, domain=d1.uuid)
    p.save()
    mario = SimpleNamespace(id="b" * 32, full_name="Mario Rossi", email="m@x.it", username="mario")
    return p, SimpleNamespace(team=team, d1=d1, d2=d2, d3=d3, section=section, clause=clause, ground=ground,
                              derived=derived, mario=mario)


def tree_of(p, user):
    from arcadia_tool.ui.model_tree import ModelTree

    tree = ModelTree()
    tree.user_of = lambda: user
    tree.set_project(p)
    return tree


def children(item):
    return [item.child(i) for i in range(item.childCount())]


def test_the_tree_has_the_specification_with_its_lists(app, tmp_path):
    from arcadia_tool.ui.model_tree import SHARED_CLAUSES, SRS_ROOT, SRS_SPEC, UNMAPPED_CLAUSES

    p, x = project(tmp_path)
    tree = tree_of(p, x.mario)
    srs = tree._srs_nodes[SRS_ROOT]
    assert srs.text(0) == "System Requirements Specifications" and srs.parent().text(0) == "Requisiti"
    spec = tree._srs_nodes[SRS_SPEC]
    assert spec.text(0) == p.baseline
    assert [c.text(0) for c in children(spec)] == ["Voci SRS", "Clausole condivise", "Clausole non mappate"]
    assert tree._kind_items["requirement"].parent() is spec
    # Not deduced: the clause has a contributor (from its section), the lists stay empty until a team declares it.
    assert tree._kind_items[SHARED_CLAUSES].childCount() == 0 and tree._kind_items[UNMAPPED_CLAUSES].childCount() == 0


def test_sharing_a_clause_creates_its_adr_filled_by_the_tool(app, tmp_path):
    from arcadia_tool.ui.model_tree import SHARED_CLAUSES

    p, x = project(tmp_path)
    tree = tree_of(p, x.mario)
    values = tree.declare_clauses(SHARED_CLAUSES, [x.clause.uuid])
    adr = next(a for a in p.model.of_kind("adr"))
    assert adr.get("adr_type") == ADR_SHARED and adr.get("status") == "Proposta"
    assert adr.get("shared_items") == [x.clause.uuid] and adr.get("title") == "Condivisione della clausola 3.5.3.7"
    assert adr.get("proposer") == x.team.uuid and adr.get("proposer_member") == "Mario Rossi"
    assert adr.get("shared_with") is None  # not proposed: the user says them
    assert shared_primary(p.model, adr) == x.d1.uuid and shared_contributors(p.model, adr) == [x.d3.uuid]
    assert values["adr_type"] == ADR_SHARED
    rows = children(tree._kind_items[SHARED_CLAUSES])
    assert [r.text(0) for r in rows] == [f"3.5.3.7 · {adr.get('id')} · Attiva"]
    selected = []
    tree.element_selected.connect(selected.append)
    tree.tree.setCurrentItem(rows[0])
    assert selected[-1] is adr  # the row opens the ADR


def test_the_ripartition_in_derived_requirements_puts_the_adr_under_their_domains(app, tmp_path):
    p, x = project(tmp_path)
    adr = p.new_element("adr", adr_type=ADR_SHARED, status="Proposta", shared_items=[x.clause.uuid])
    assert shared_derived(p.model, adr) == [(x.derived.uuid, p.model.choice_label(x.derived))]
    adr.set("share_split", [{"derived": x.derived.uuid, "domain": x.d2.uuid},
                            {"description": "Un sottorequisito ancora da derivare", "domain": x.d3.uuid}])
    p.update(adr)
    assert adr in related_adrs(p.model, x.d2)  # among the ADR of the domain of destination
    assert {d.uuid for d in impacted_domains(p.model, adr)} >= {x.d2.uuid, x.d3.uuid}
    from arcadia_tool.model.notifications import destination_teams
    assert x.team.uuid in destination_teams(p.model, adr)  # the team of the domain of destination is told
    changed = approve_sharing(p, adr)
    assert x.derived.get("domain") == x.d2.uuid and x.derived in changed  # to its domain of destination
    assert x.clause.get("contributing_domains") == [x.d3.uuid, x.d2.uuid]  # the one of the section stays
    assert outcome(adr) == APPROVED and adr.get("share_applied")
    assert shared_contributors(p.model, adr) == [x.d3.uuid]  # as they were: the ADR does not change


def test_a_clause_mapped_to_no_domain(app, tmp_path):
    from arcadia_tool.checks import run
    from arcadia_tool.ui.model_tree import UNMAPPED_CLAUSES

    p, x = project(tmp_path)
    tree = tree_of(p, x.mario)
    tree.declare_clauses(UNMAPPED_CLAUSES, [x.ground.uuid])
    adr = next(a for a in p.model.of_kind("adr"))
    assert adr.get("adr_type") == ADR_UNMAPPED and adr.get("unmapped_reason") == "Requisito di terra"
    assert unmapped_sections(p.model, adr) == [x.section.uuid]
    assert unmapped_section_domains(p.model, adr) == [x.d1.uuid]
    assert [r.text(0).split(" · ")[0] for r in children(tree._kind_items[UNMAPPED_CLAUSES])] == ["3.5.3.8"]
    assert not unmapped_by_decision(p.model)  # proposed: not yet a decision
    approve_unmapped(p, adr)
    assert outcome(adr) == APPROVED and unmapped_by_decision(p.model) == {x.ground.uuid}
    assert x.ground.get("primary_domain") is None and not x.ground.get("contributing_domains")  # not changed
    # A section mapped to no domain by decision is not a gap any more (A4-01).
    section = p.new_element("requirement", id="3.6.1", item_type="Sezione")
    other = p.new_element("adr", adr_type=ADR_UNMAPPED, status="Proposta", unmapped_items=[section.uuid])
    findings = lambda: [f for f in run(p.model, ["A4-01"]) if f.element == section.uuid]
    assert findings()
    approve_unmapped(p, other)
    assert not findings()


def test_the_catalogue_lists_every_adr_also_closed(app, tmp_path):
    from arcadia_tool.ui.clause_catalog import ClauseCatalog

    p, x = project(tmp_path)
    first = p.new_element("adr", adr_type=ADR_SHARED, status="Proposta", shared_items=[x.clause.uuid],
                          shared_with=[x.d2.uuid])
    approve_sharing(p, first)
    second = p.new_element("adr", adr_type=ADR_SHARED, status="Proposta", shared_items=[x.clause.uuid],
                           da_decision="Respinta")
    assert [a for _i, a in clause_decisions(p.model, ADR_SHARED)] == [first, second]
    catalog = ClauseCatalog(p, ADR_SHARED)
    assert catalog.table.rowCount() == 2
    outcomes = [catalog.table.item(r, 5).text() for r in range(2)]
    assert outcomes == ["Approvata", "Respinta"]
    header = catalog.table.horizontalHeader()
    for c in range(catalog.table.columnCount()):  # every heading readable whole
        if c != 1:  # «Testo» takes the rest of the width
            text = catalog.table.horizontalHeaderItem(c).text()
            assert header.sectionSize(c) >= header.fontMetrics().horizontalAdvance(text) + 20, text
    opened = []
    catalog.open_requested.connect(opened.append)
    catalog.table.selectRow(1)
    catalog.open_adr()
    assert opened == [second.uuid]
    catalog.search.setText("nessuna corrispondenza")
    assert all(catalog.table.isRowHidden(r) for r in range(2))


def test_the_catalogue_opens_in_a_tab(app, tmp_path):
    from arcadia_tool.ui import main_window as mw
    from arcadia_tool.ui.clause_catalog import ClauseCatalog
    from arcadia_tool.ui.model_tree import SHARED_CLAUSES, UNMAPPED_CLAUSES

    p, x = project(tmp_path)
    adr = p.new_element("adr", adr_type=ADR_SHARED, status="Proposta", shared_items=[x.clause.uuid])
    p.save()
    window = mw.MainWindow()
    window._set_project(p)
    window.tree._double_clicked(window.tree._kind_items[SHARED_CLAUSES], 0)  # a double click on the list
    page = window.pages.currentWidget()
    assert isinstance(page, ClauseCatalog) and window.pages.tabText(window.pages.currentIndex()) == "Clausole condivise"
    tabs = window.pages.count()
    window.open_clause_catalog(SHARED_CLAUSES)  # again: the same tab
    assert window.pages.count() == tabs and window.pages.currentWidget() is page
    declared = []
    window.tree.declare_clauses = declared.append  # «Nuova…»: the same as from the menu of the list
    page.new_button.click()
    window.open_clause_catalog(UNMAPPED_CLAUSES)
    assert window.pages.count() == tabs + 1
    window.pages.currentWidget().new_button.click()
    assert declared == [SHARED_CLAUSES, UNMAPPED_CLAUSES]
    previous = adr.copy()
    adr.set("shared_with", [x.d2.uuid])  # an ADR changed: the tab follows it
    p.update(adr, previous)
    window._element_changed(adr)
    assert page.table.item(0, 3).text() == x.d2.get("id")
    window._set_project(None)  # the project goes, its tabs with it
    assert SHARED_CLAUSES not in window.list_pages
    window.close()


def test_the_clauses_are_chosen_in_the_window_of_the_traceability(app, tmp_path, monkeypatch):
    from arcadia_tool.ui import srs_trace
    from arcadia_tool.ui.model_tree import SHARED_CLAUSES, UNMAPPED_CLAUSES

    p, x = project(tmp_path)
    tree = tree_of(p, x.mario)
    opened = []

    def exec_(dialog):  # the same window as for the clauses of a system function: one clause ticked
        opened.append(dialog)
        dialog.set_state(x.clause.uuid, srs_trace.PARENT)
        return True
    monkeypatch.setattr(srs_trace.TraceItemsDialog, "exec", exec_)
    tree.declare_clauses(SHARED_CLAUSES)
    assert isinstance(opened[0], srs_trace._TraceDialog) and "Clausole da condividere" in opened[0].HINT
    adr = next(a for a in p.model.of_kind("adr"))
    assert adr.get("shared_items") == [x.clause.uuid]
    monkeypatch.setattr(srs_trace.TraceItemsDialog, "exec", lambda dialog: False)  # cancelled: no ADR
    assert tree.declare_clauses(UNMAPPED_CLAUSES) is None and len(p.model.of_kind("adr")) == 1


def test_the_buttons_of_a_clause_in_the_srs_catalogue(app, tmp_path):
    from arcadia_tool.ui.srs_reader import ROW_ACTIONS, SrsReader
    from arcadia_tool.ui.model_tree import SHARED_CLAUSES, UNMAPPED_CLAUSES

    assert [name for name, _l, _t in ROW_ACTIONS["clause"]] == ["functions", "derive", "share", "exclude"]
    assert [label for _n, label, _t in ROW_ACTIONS["clause"]][2:] == ["Condividi", "Escludi"]
    p, x = project(tmp_path)
    reader = SrsReader(p)
    asked = []
    reader.clause_declared.connect(lambda key, uuid: asked.append((key, uuid)))
    reader.run_action(x.clause.uuid, "share")
    reader.run_action(x.ground.uuid, "exclude")
    assert asked == [(SHARED_CLAUSES, x.clause.uuid), (UNMAPPED_CLAUSES, x.ground.uuid)]
    # From the main window: the ADR of the clause, created at once.
    from arcadia_tool.ui import main_window as mw
    window = mw.MainWindow()
    window._set_project(p)
    window.user = x.mario
    window.tree.user_of = lambda: x.mario
    window.open_srs_reader()
    window.reader.run_action(x.clause.uuid, "share")
    adr = next(a for a in p.model.of_kind("adr"))
    assert adr.get("adr_type") == ADR_SHARED and adr.get("shared_items") == [x.clause.uuid]
    window._set_project(None)
    window.close()


def test_the_sections_show_the_badge_of_their_domain(app, tmp_path):
    from arcadia_tool.ui.model_tree import BADGE_ROLE, section_badge

    p, x = project(tmp_path)
    tree = tree_of(p, x.mario)
    d1 = p.model.get(x.d1.uuid)
    expected = f"{d1.get('id')} · Odometria"
    assert section_badge(p.model, x.section) == expected
    assert tree._items[x.section.uuid].data(0, BADGE_ROLE) == expected
    assert tree._items[x.clause.uuid].data(0, BADGE_ROLE) is None  # a clause: no badge
    previous = x.section.copy()
    x.section.set("primary_domain", x.d2.uuid)  # assigned to another domain
    p.update(x.section, previous)
    tree.refresh_label(x.section)
    assert tree._items[x.section.uuid].data(0, BADGE_ROLE).endswith("Radio")
    previous = x.d2.copy()
    x.d2.set("name", "Radio GSM-R")  # the domain renamed: its sections follow
    p.update(x.d2, previous)
    tree.refresh_label(x.d2)
    assert tree._items[x.section.uuid].data(0, BADGE_ROLE).endswith("Radio GSM-R")
    tree.resize(500, 400)
    tree.show()
    tree.select(x.section.uuid)
    app.processEvents()
    assert not tree.grab().isNull()  # drawn with the badge
    tree.close()  # not left on screen: it would take the mouse of the tests that follow
    tree.deleteLater()
    app.processEvents()

