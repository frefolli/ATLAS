"""An ADR about SRS sections or clauses, opened by a team: the sections (three numbers, e.g. 3.4.1) must be held by one
of its functional domains, else the user is asked whether to save it all the same."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from arcadia_tool.model.adr import sections_not_held
from arcadia_tool.model.schema import ADR_EXCLUSION, ADR_SECTION, ADR_SHARED, ADR_UNMAPPED
from arcadia_tool.storage.project import Project
from arcadia_tool.ui import element_editor
from arcadia_tool.ui.element_editor import ElementEditor


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def build(tmp_path):
    p = Project.create(tmp_path / "p", "Prova")
    rfi, fbk = p.new_element("team", name="RFI"), p.new_element("team", name="FBK")
    mine = p.new_element("domain", name="Mio", team=rfi.uuid)
    theirs = p.new_element("domain", name="Loro", team=fbk.uuid)
    chapter = p.new_element("requirement", id="3.4", item_type="Capitolo")
    own = p.new_element("requirement", id="3.4.1", item_type="Sezione", parent=chapter.uuid, primary_domain=mine.uuid)
    other = p.new_element("requirement", id="3.4.2", item_type="Sezione", parent=chapter.uuid,
                          primary_domain=theirs.uuid, contributing_domains=[mine.uuid])
    c1 = p.new_element("requirement", id="3.4.1.5", item_type="Requisito", parent=own.uuid)
    c2 = p.new_element("requirement", id="3.4.2.1", item_type="Requisito", parent=other.uuid)
    c3 = p.new_element("requirement", id="3.4.2.2", item_type="Requisito", parent=other.uuid)
    return p, dict(rfi=rfi, fbk=fbk, mine=mine, theirs=theirs, own=own, other=other, c1=c1, c2=c2, c3=c3)


def test_the_sections_not_held_by_the_team(tmp_path):
    p, e = build(tmp_path)

    def adr(adr_type, field, items, team="rfi"):
        return p.new_element("adr", adr_type=adr_type, status="Proposta", proposer=e[team].uuid,
                             **{field: [e[i].uuid for i in items]})
    assert sections_not_held(p.model, adr(ADR_SECTION, "realloc_item", ["c1", "own"])) == []
    # A contributor does not hold the section: only the principal domain does; each section once.
    assert sections_not_held(p.model, adr(ADR_SHARED, "shared_items", ["c1", "c2", "c3"])) == \
        [(e["other"], e["theirs"].uuid)]
    assert sections_not_held(p.model, adr(ADR_UNMAPPED, "unmapped_items", ["other"])) == [(e["other"], e["theirs"].uuid)]
    assert sections_not_held(p.model, adr(ADR_EXCLUSION, "excluded_item", ["c2"], team="fbk")) == []
    # A clause passed to a domain of the team by a reallocation: held, though its section is not.
    e["c2"].set("primary_domain", e["mine"].uuid)
    assert sections_not_held(p.model, adr(ADR_SHARED, "shared_items", ["c2", "c3"])) == [(e["other"], e["theirs"].uuid)]
    assert sections_not_held(p.model, adr(ADR_SHARED, "shared_items", ["c2"])) == []
    # No team proposing it: nothing to compare.
    unproposed = p.new_element("adr", adr_type=ADR_SECTION, status="Proposta", realloc_item=[e["c3"].uuid])
    assert sections_not_held(p.model, unproposed) == []


def test_the_sheet_says_it_to_everyone(app, tmp_path):
    from PySide6.QtWidgets import QFrame, QLabel

    p, e = build(tmp_path)
    adr = p.new_element("adr", title="Spostare", adr_type=ADR_SECTION, status="Superata", proposer=e["rfi"].uuid,
                        realloc_item=[e["c2"].uuid, e["c1"].uuid])
    editor = ElementEditor()
    editor.edit(p, adr)  # read-only, whoever reads it (the Design Authority too)
    frame = editor.findChild(QFrame, "sectionsNotHeld")
    assert frame is not None
    text = " ".join(label.text() for label in frame.findChildren(QLabel))
    assert "sezione <a href='%s'>3.4.2</a>" % e["other"].uuid in text and "FBK" in text and "RFI" in text
    assert "3.4.1<" not in text  # its own section: not said
    opened = []
    editor.open_requested.connect(opened.append)
    [label for label in frame.findChildren(QLabel) if "3.4.2" in label.text()][0].linkActivated.emit(e["other"].uuid)
    assert opened == [e["other"].uuid]
    adr.set("realloc_item", [e["c1"].uuid])
    editor = ElementEditor()
    editor.edit(p, adr)
    assert editor.findChild(QFrame, "sectionsNotHeld") is None
    p.close()


def test_saving_the_adr_asks_whether_the_choice_is_right(app, tmp_path, monkeypatch):
    p, e = build(tmp_path)
    asked, answer = [], [QMessageBox.No]
    monkeypatch.setattr(element_editor.QMessageBox, "question", lambda *a, **k: asked.append(a[2]) or answer[0])
    adr = p.new_element("adr", title="Spostare", adr_type=ADR_SECTION, status="Proposta", proposer=e["rfi"].uuid,
                        proposer_member="Anna", realloc_item=[e["c2"].uuid], primary_proposed=e["mine"].uuid,
                        realloc_reason="Perché")
    editor = ElementEditor()
    editor.edit(p, adr, editing=True)
    editor.unsaved_new = True
    editor.draft.set("title", "Spostare 3.4.2.1")
    editor.dirty = True  # written by the user
    assert editor.save_changes() is False and editor.editing  # answered no: still to save
    assert len(asked) == 1 and "3.4.2 (DF02, team" in asked[0] and "FBK" in asked[0] and "RFI" in asked[0]
    answer[0] = QMessageBox.Yes
    assert editor.save_changes() is not False and not editor.editing
    assert len(asked) == 2 and adr.get("title") == "Spostare 3.4.2.1"
    # Saved again with the SRS items and the team as they were: nothing asked.
    editor.start_editing()
    editor.draft.set("realloc_reason", "Perché sì")
    editor.dirty = True
    editor.save_changes()
    assert len(asked) == 2
    # A section of its own: nothing asked.
    editor.start_editing()
    editor.draft.set("realloc_item", [e["c1"].uuid])
    editor.dirty = True
    editor.save_changes()
    assert len(asked) == 2 and adr.get("realloc_item") == [e["c1"].uuid]
    p.close()


def test_the_choice_of_the_items_to_reallocate_shows_the_own_domains_first(app, tmp_path):
    from arcadia_tool.ui import srs_trace

    p, e = build(tmp_path)
    e["c2"].set("primary_domain", e["mine"].uuid)  # passed to the team by a reallocation
    adr = p.new_element("adr", adr_type=ADR_SECTION, status="Proposta", proposer=e["rfi"].uuid)
    dialog = srs_trace.TraceReallocItemsDialog(p, adr.copy(), "realloc_item")

    def shown():
        found, it = [], srs_trace.QTreeWidgetItemIterator(dialog.tree)
        while it.value():
            if not it.value().isHidden():
                found.append(p.model.get(it.value().data(0, srs_trace.UUID_ROLE)).get("id"))
            it += 1
        return found
    assert dialog.own_box.isChecked() and dialog.own_box.text() == "Propri domini"
    row = dialog.filters_row
    assert row.indexOf(dialog.own_box) == row.indexOf(dialog.sections_only) + 1  # right after «Solo sezioni»
    assert shown() == ["3.4", "3.4.1", "3.4.1.5", "3.4.2", "3.4.2.1"]  # 3.4.2.2: of the other team
    dialog.sections_only.setChecked(True)
    assert shown() == ["3.4", "3.4.1"]
    dialog.sections_only.setChecked(False)
    dialog.own_box.setChecked(False)
    assert shown() == ["3.4", "3.4.1", "3.4.1.5", "3.4.2", "3.4.2.1", "3.4.2.2"]
    # One chosen of another team stays shown, to be unticked.
    other = adr.copy()
    other.set("realloc_item", [e["c3"].uuid])
    dialog = srs_trace.TraceReallocItemsDialog(p, other, "realloc_item")
    assert "3.4.2.2" in shown()
    # No team proposing it: nothing to filter on.
    unproposed = p.new_element("adr", adr_type=ADR_SECTION, status="Proposta")
    dialog = srs_trace.TraceReallocItemsDialog(p, unproposed.copy(), "realloc_item")
    assert not dialog.own_box.isChecked() and not dialog.own_box.isEnabled()
    assert "3.4.2.2" in shown()
    p.close()
