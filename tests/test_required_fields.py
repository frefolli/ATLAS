"""Mandatory fields: a domain and a system function are saved only when complete; one just created and incomplete goes
away with its sheet. Their references, and those of an ADR, are chosen in a window instead of a drop-down list."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QComboBox, QMessageBox

from arcadia_tool.model.required import missing_fields
from arcadia_tool.model.schema import ADR_SECTION
from arcadia_tool.storage.project import Project
from arcadia_tool.ui.element_editor import ElementEditor, resolve_unsaved
from arcadia_tool.ui.main_window import MainWindow


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def warnings(monkeypatch):
    said = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: said.append(a[2]) or QMessageBox.Ok)
    return said


def build(tmp_path):
    p = Project.create(tmp_path / "p", "Prova")
    section = p.new_element("requirement", id="3.8.1", item_type="Sezione", title="Una sezione")
    clause = p.new_element("requirement", id="3.8.1.1", item_type="Requisito", parent=section.uuid, text="Una clausola")
    p.save()
    return p, section, clause


def window_on(p):
    window = MainWindow()
    window._set_project(p)
    return window


def test_what_a_domain_and_a_function_must_have(tmp_path):
    p, section, clause = build(tmp_path)
    domain = p.new_element("domain")
    assert missing_fields(p.model, domain) == ["Nome", "Missione", "Almeno una sezione SRS mappata"]
    domain.set("name", "Odometria")
    domain.set("mission", "   ")
    assert missing_fields(p.model, domain) == ["Missione", "Almeno una sezione SRS mappata"]
    domain.set("mission", "Misura il moto.")
    section.set("contributing_domains", [domain.uuid])  # principal or contributing
    assert missing_fields(p.model, domain) == []
    function = p.new_element("system_function", domain=domain.uuid)
    assert len(missing_fields(p.model, function)) == 3 and missing_fields(p.model, function)[-1] == "Clausole SRS mappate"
    function.set("name", "Rileva il moto")
    function.set("description", "Rileva il moto del treno.")
    function.set("sections", [clause.uuid])
    assert missing_fields(p.model, function) == []
    assert missing_fields(p.model, p.new_element("team")) == []  # the other sheets: as before


def test_saving_without_them_says_what_is_missing_and_keeps_the_sheet(app, tmp_path, warnings):
    p, section, clause = build(tmp_path)
    window = window_on(p)
    window.tree.create("domain")
    domain = p.model.of_kind("domain")[0]
    editor = window.editors[domain.uuid]
    assert editor.unsaved_new
    assert editor.save_changes() is False
    assert "Missione" in warnings[0] and "Almeno una sezione SRS mappata" in warnings[0]
    assert editor.unsaved_new and p.is_new(domain)
    # Complete: saved.
    editor.widgets["name"].setText("Odometria")
    editor.widgets["mission"].editor.setPlainText("Misura il moto.")
    section.set("primary_domain", domain.uuid)
    p.update(section)
    editor.save_changes()
    assert not editor.unsaved_new and not p.is_new(domain) and len(warnings) == 1
    # An existing sheet too, at its next change: not saved, and the model does not change.
    editor.start_editing()
    editor.widgets["mission"].editor.setPlainText("")
    assert editor.save_changes() is False and domain.get("mission") == "Misura il moto."
    assert "Missione" in warnings[1]
    editor.cancel_changes(ask=False)
    window._set_project(None)
    window.close()


def test_a_new_incomplete_domain_goes_away_with_its_sheet_and_what_it_mapped(app, tmp_path, warnings):
    p, section, clause = build(tmp_path)
    window = window_on(p)
    window.tree.create("domain")
    domain = p.model.of_kind("domain")[0]
    section.set("primary_domain", domain.uuid)  # as the window of the traceability does, at once
    p.update(section)
    assert domain.uuid in window.tree._items
    window._close_page(window.pages.indexOf(window.editors[domain.uuid]))
    assert p.model.get(domain.uuid) is None and domain.uuid not in window.tree._items
    assert not section.get("primary_domain") and not p.is_modified  # back as it was
    window._set_project(None)
    window.close()


def test_the_toolbar_does_not_write_a_new_incomplete_sheet(app, tmp_path, warnings):
    p, section, clause = build(tmp_path)
    other = p.new_element("team", name="Un team")
    window = window_on(p)
    window.tree.create("domain")
    domain = p.model.of_kind("domain")[0]
    window.save()
    assert p.is_new(domain) and p.model.get(domain.uuid) is not None and "Missione" in warnings[0]
    assert not p.is_new(other)  # the rest is saved
    window.save_tab()
    assert len(warnings) == 2 or p.is_new(domain)
    assert not window._no_incomplete_new()  # publishing, changing branch: asked to complete it first
    window._set_project(None)
    window.close()


def test_a_failed_save_in_the_question_keeps_the_sheet_open(app, tmp_path, warnings, monkeypatch):
    p, section, clause = build(tmp_path)
    window = window_on(p)
    window.tree.create("domain")
    editor = window.editors[p.model.of_kind("domain")[0].uuid]
    editor.widgets["name"].setText("Odometria")
    editor.flush()
    assert editor.dirty

    class Box(QMessageBox):
        def exec(self):
            return 0

        def clickedButton(self):
            return next(b for b in self.buttons() if b.text() == "Salva")
    monkeypatch.setattr("arcadia_tool.ui.element_editor.QMessageBox", Box)
    Box.warning = staticmethod(lambda *a, **k: warnings.append(a[2]))
    assert resolve_unsaved(editor, window) is False and warnings
    monkeypatch.undo()
    editor.cancel_changes(ask=False)
    window._set_project(None)
    window.close()


def test_a_new_function_gives_back_the_derived_requirements_it_mapped(tmp_path):
    p, section, clause = build(tmp_path)
    domain = p.new_element("domain", name="Odometria")
    function = p.new_element("system_function", domain=domain.uuid)
    derived = p.new_element("derived_requirement", parent=clause.uuid, obligation="Uno.", system_function=function.uuid)
    assert p.discard_new(function.uuid)
    assert not derived.get("system_function")


@pytest.mark.parametrize("kind,field", [("domain", "team"), ("system_function", "domain"), ("adr", "proposer")])
def test_the_references_are_chosen_in_a_window(app, tmp_path, monkeypatch, kind, field):
    p, section, clause = build(tmp_path)
    team = p.new_element("team", name="Un team")
    domain = p.new_element("domain", name="Odometria")
    values = {"adr_type": ADR_SECTION} if kind == "adr" else {}
    element = domain if kind == "domain" else p.new_element(kind, **values)
    editor = ElementEditor()
    editor.edit(p, element)
    editor.start_editing()
    assert not [c for c in editor.findChildren(QComboBox) if c.currentData() is None and c.count() > 1
                and c.itemData(1) in (team.uuid, domain.uuid)]  # no drop-down list of the elements
    target = domain if field == "domain" else team
    monkeypatch.setattr("arcadia_tool.ui.srs_trace.choose_element", lambda *a, **k: target.uuid)
    editor._pick(element.schema.field(field))
    assert editor.draft.get(field) == target.uuid
    assert editor.dirty
    assert editor.getters[field]() == target.uuid
    editor.cancel_changes(ask=False)


def test_an_empty_sheet_of_the_system_analysis_or_an_adr_is_not_saved(app, tmp_path, warnings):
    from arcadia_tool.model.required import EMPTY_SHEET, is_blank, must_not_be_empty, save_refusal
    from arcadia_tool.model.schema import KINDS_BY_NAME as K

    assert all(must_not_be_empty(K[n]) for n in ("adr", "functional_chain", "exchange_item", "trace_record",
                                                 "derived_requirement", "external_actor"))
    assert not any(must_not_be_empty(K[n]) for n in ("team", "clarification", "logical_function"))
    p, section, clause = build(tmp_path)
    window = window_on(p)
    window.tree.create("adr", {"adr_type": ADR_SECTION, "status": "Proposta"})  # the type and the status: by the tool
    decision = p.model.of_kind("adr")[0]
    editor = window.editors[decision.uuid]
    assert is_blank(editor.draft) and editor.save_changes() is False and warnings == [EMPTY_SHEET]
    assert p.is_new(decision)
    editor.widgets["title"].setText("Spostamento")
    editor.save_changes()
    assert not p.is_new(decision) and len(warnings) == 1
    # Created from an element, and left as it was: nothing written by the user.
    new = p.new_element("adr", adr_type=ADR_SECTION, realloc_item=[clause.uuid])
    assert not is_blank(new) and save_refusal(p.model, new, untouched=True) == EMPTY_SHEET
    assert save_refusal(p.model, new) is None
    # A chain: the same, and the toolbar does not write it.
    window.tree.create("functional_chain")
    chain = p.model.of_kind("functional_chain")[0]
    window.save()
    assert p.is_new(chain) and warnings[-1] == EMPTY_SHEET
    window._close_page(window.pages.indexOf(window.editors[chain.uuid]))
    assert p.model.get(chain.uuid) is None
    window._set_project(None)
    window.close()


def test_the_proposer_of_a_new_adr_is_the_user_and_the_team(app, tmp_path):
    from types import SimpleNamespace
    from arcadia_tool.model.adr import exclusion_defaults, proposer_defaults

    p, section, clause = build(tmp_path)
    team = p.new_element("team", name="FBK", members=[{"name": "Mario Rossi", "account": "b" * 32}])
    mario = SimpleNamespace(id="b" * 32, full_name="Mario Rossi", email="m@x.it", username="mario")
    anna = SimpleNamespace(id="a" * 32, full_name="Anna Bianchi", email="a@x.it", username="anna")
    assert proposer_defaults(p.model, mario) == {"proposer": team.uuid, "proposer_member": "Mario Rossi"}
    assert proposer_defaults(p.model, anna) == {} and proposer_defaults(p.model, None) == {}
    window = window_on(p)
    window.user = mario
    window.tree.create("adr", {"adr_type": ADR_SECTION, "status": "Proposta"})
    decision = p.model.of_kind("adr")[0]
    assert decision.get("proposer") == team.uuid and decision.get("proposer_member") == "Mario Rossi"
    editor = window.editors[decision.uuid]
    assert editor.widgets["proposer_member"].value() == "Mario Rossi"  # shown, and it can be changed
    window.user = anna  # in no team: left to the user
    window.tree.create("adr", {"adr_type": ADR_SECTION, "status": "Proposta"})
    other = next(a for a in p.model.of_kind("adr") if a is not decision)
    assert not other.get("proposer") and not other.get("proposer_member")
    window._set_project(None)
    window.close()


def test_no_drop_down_list_in_the_sheets_of_domains_functions_and_adr(app, tmp_path, monkeypatch):
    from arcadia_tool.model.schema import ADR_TYPE_LABELS
    from arcadia_tool.ui import element_editor as ee

    p, section, clause = build(tmp_path)
    domain = p.new_element("domain", name="Odometria")
    function = p.new_element("system_function", name="Rileva", domain=domain.uuid)
    editor = ElementEditor()
    for element in (domain, function, *(p.new_element("adr", title=t, adr_type=t) for t in ADR_TYPE_LABELS)):
        editor.edit(p, element, editing=True)
        assert not editor.findChildren(QComboBox), element.get("adr_type") or element.kind
    # The decision of the DA, in its window with search; «Nessuno» empties it.
    adr = p.model.of_kind("adr")[0]
    editor.edit(p, adr, editing=True)
    picker = editor.widgets["da_decision"]
    picker.button.setEnabled(True)
    seen = []

    def run(dialog):
        seen.append([dialog.list.item(i).text() for i in range(dialog.list.count())])
        dialog.search.setText("respinta")
        assert [dialog.list.item(i).isHidden() for i in range(dialog.list.count())].count(False) == 1
        dialog.list.setCurrentRow(seen[0].index("Respinta"))
        return True
    monkeypatch.setattr(ee.ChoiceDialog, "exec", run)
    picker.choose()
    assert seen[0][0] == "Nessuno" and "Accolta" in seen[0] and picker.value() == "Respinta"
    assert picker.shown.text() == "Respinta" and editor.getters["da_decision"]() == "Respinta" and editor.dirty
    # The state too: the chip opens the same window.
    status = editor.widgets["status"]
    monkeypatch.setattr(ee.ChoiceDialog, "exec", lambda d: d.list.setCurrentRow(1) or True)
    status.choose()
    assert status.text() == status.value() == adr.schema.field("status").options[0]
    editor.cancel_changes(ask=False)

