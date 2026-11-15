"""«Modifiche locali»: the local changes in order, the last one discarded and the last discarded restored, one at a
time; kept with the project until they are published."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from arcadia_tool.storage.journal import BASELINE_LABEL, JournalError
from arcadia_tool.storage.project import Project

AUTHOR = "Prova <prova@example.com>"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def published(tmp_path):
    p = Project.create(tmp_path / "p", "Prova")
    p.new_element("domain", name="Odometria")
    p.save()
    p.publish("v1", AUTHOR)
    p.journal.record()  # what was done before publishing: published, not local
    p.journal.check_head()
    return p


def names(project):
    return sorted(d.get("name") for d in project.model.of_kind("domain"))


def test_each_action_is_an_entry_discarded_and_restored_one_at_a_time(tmp_path):
    p = published(tmp_path)
    j = p.journal
    radio = p.new_element("domain", name="Radio")
    first = j.record()
    assert first.label.startswith("Creato") and "DF02 Radio" in first.label
    odometry = next(d for d in p.model.of_kind("domain") if d.get("name") == "Odometria")
    odometry.set("name", "Odometria e localizzazione")  # as a sheet does: the element changed, then the project told
    p.update(odometry)
    second = j.record()
    assert second.label.startswith("Modificato") and [c.uuid for c in second.changes] == [odometry.uuid]
    assert j.record() is None  # nothing more
    assert j.undo() == [second] and names(p) == ["Odometria", "Radio"]
    assert j.undo() == [first] and names(p) == ["Odometria"]
    assert j.undo() == []
    assert j.redo() == [first] and names(p) == ["Odometria", "Radio"]
    assert p.model.get(radio.uuid).get("id") == "DF02"
    # A new change not linked to the one discarded: it can still be restored.
    p.new_element("domain", name="Frenatura")
    j.record()
    assert j.last_undone() is second and [e.undone for e in j.entries] == [False, True, False]
    # A new change of the same element: the one discarded can no longer be restored, it leaves the list.
    odometry = p.model.get(odometry.uuid)
    odometry.set("description", "Posizione del treno")
    p.update(odometry)
    j.record()
    assert j.last_undone() is None and len(j.entries) == 3


def test_an_earlier_change_is_discarded_with_the_later_ones_linked_and_restored_with_those_it_needs(tmp_path):
    p = published(tmp_path)
    j = p.journal
    radio = p.new_element("domain", name="Radio")
    created = j.record()
    braking = p.new_element("domain", name="Frenatura")
    other = j.record()
    session = p.new_element("system_function", name="Stabilire la sessione", domain=radio.uuid)
    function = j.record()  # it refers to Radio, created by the first entry
    radio = p.model.get(radio.uuid)
    radio.set("description", "Comunicazione via radio")
    p.update(radio)
    described = j.record()  # Radio again
    assert j.to_undo(created) == [created, function, described]
    assert j.to_undo(other) == [other]
    assert j.undo(created) == [created, function, described]
    assert names(p) == ["Frenatura", "Odometria"] and p.model.get(session.uuid) is None
    assert [e.undone for e in j.entries] == [True, False, True, True]
    assert j.last_done() is other
    # Restoring the function: the domain it needs comes back too (not its description, which needs neither).
    assert j.to_redo(function) == [created, function]
    assert j.redo(function) == [created, function]
    assert p.model.get(session.uuid) is not None and names(p) == ["Frenatura", "Odometria", "Radio"]
    assert p.model.get(radio.uuid).get("description") in (None, "")
    assert j.redo() == [described] and p.model.get(radio.uuid).get("description") == "Comunicazione via radio"
    assert p.model.get(braking.uuid) is not None
    # Saved and opened again: the discarded entries, also in the middle, are still there.
    j.undo(created)
    p.save()
    again = Project.open(p.path)
    assert [e.undone for e in again.journal.entries] == [True, False, True, True]


def test_an_identifier_given_again_links_two_changes(tmp_path):
    p = published(tmp_path)
    j = p.journal
    braking = p.new_element("domain", name="Frenatura")
    p.save()
    p.publish("v2", AUTHOR)
    j.check_head()
    p.delete_element(braking.uuid)
    deleted = j.record()
    radio = p.new_element("domain", name="Radio")
    assert radio.get("id") == "DF02"
    created = j.record()
    # Frenatura back (its deletion discarded) and Radio still DF02: two DF02. Radio goes with it.
    assert j.to_undo(deleted) == [deleted, created]


def test_the_entries_stay_with_the_project_saved(tmp_path):
    p = published(tmp_path)
    p.new_element("domain", name="Radio")
    p.journal.record()
    p.new_element("domain", name="Frenatura")
    p.journal.record()
    p.journal.undo()
    p.save()
    again = Project.open(p.path)
    assert [e.undone for e in again.journal.entries] == [False, True]
    assert again.journal.redo() and names(again) == ["Frenatura", "Odometria", "Radio"]
    again.save()
    stale = again.journal.file.read_text(encoding="utf-8")
    # The model changed without them (e.g. by an ATLAS without this function): they no longer fit, they start again.
    p2 = Project.open(p.path)
    radio = next(d for d in p2.model.of_kind("domain") if d.get("name") == "Radio")
    radio.set("name", "Radio GSM-R")
    p2.update(radio)
    p2.save()
    p2.journal.file.write_text(stale, encoding="utf-8")
    assert Project.open(p.path).journal.entries == []


def test_publishing_empties_the_entries_and_older_changes_are_one_entry(tmp_path):
    p = published(tmp_path)
    p.new_element("domain", name="Radio")
    p.journal.record()
    p.save()
    p.publish("v2", AUTHOR)
    p.new_element("domain", name="Frenatura")
    entry = p.journal.record()
    assert p.journal.entries == [entry]  # the entry of Radio, published, is gone
    # Changes not in the entries (made before): «Modifiche precedenti», the first entry, discarded last.
    p.journal.entries = []
    p.save()
    assert p.journal.add_baseline().label == BASELINE_LABEL
    assert p.journal.add_baseline() is None  # once
    assert [e.label for e in p.journal.undo()] == [BASELINE_LABEL] and names(p) == ["Odometria", "Radio"]
    p.save()
    assert not p.has_unpublished_changes()  # back to the last version
    assert [e.label for e in p.journal.redo()] == [BASELINE_LABEL] and names(p) == ["Frenatura", "Odometria", "Radio"]


def test_an_element_changed_in_another_way_is_not_put_back(tmp_path):
    p = published(tmp_path)
    radio = p.new_element("domain", name="Radio")
    entry = p.journal.record()
    radio.set("name", "Radio GSM-R")  # changed and never told to the project: not in an entry
    with pytest.raises(JournalError):
        p.journal.undo(entry)


def test_the_window_lists_the_changes_and_puts_them_back_one_at_a_time(app, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QToolBar

    from arcadia_tool.ui import main_window as mw
    from arcadia_tool.ui.local_changes import LocalChangesDialog

    p = published(tmp_path)
    window = mw.MainWindow()
    window._set_project(p)
    actions = window.findChild(QToolBar).actions()
    assert actions.index(window.local_changes_action) == actions.index(window.history_action) - 1
    assert window.local_changes_action.shortcut().toString() == "Ctrl+Alt+Z"
    radio = p.new_element("domain", name="Radio")
    window._record_change()  # the action ended (the timer)
    odometry = next(d for d in p.model.of_kind("domain") if d.get("name") == "Odometria")
    window._select(odometry)  # its sheet open
    odometry.set("name", "Odometria e localizzazione")
    p.update(odometry)
    shown = []

    def run(dialog):
        shown.append(dialog)
        assert [dialog.list.topLevelItem(i).text(1) for i in range(dialog.list.topLevelItemCount())][-1].startswith(
            "Modificato")
        dialog.undo_button.click()  # the renaming discarded
        assert window.editors[odometry.uuid].element.get("name") == "Odometria"  # the open sheet shows it
        dialog.undo_button.click()  # Radio discarded
        assert names(window.project) == ["Odometria"] and not dialog.undo_button.isEnabled()
        dialog.redo_button.click()  # Radio back
        assert dialog.redo_button.isEnabled() and "1 scartate" in dialog.state.text()
        return 0
    monkeypatch.setattr(LocalChangesDialog, "exec", run)
    window.local_changes_action.trigger()
    assert shown and names(p) == ["Odometria", "Radio"]
    assert p.model.get(radio.uuid) is not None
    window._set_project(None)
    window.close()


def test_the_window_discards_the_entry_chosen_with_those_linked_highlighted(app, tmp_path):
    from arcadia_tool.ui.local_changes import LINKED_BG, LocalChangesDialog

    p = published(tmp_path)
    j = p.journal
    radio = p.new_element("domain", name="Radio")
    j.record()
    p.new_element("domain", name="Frenatura")
    j.record()
    p.new_element("system_function", name="Stabilire la sessione", domain=radio.uuid)
    j.record()
    dialog = LocalChangesDialog(p)
    items = dialog._items()
    dialog.list.setCurrentItem(items[0])  # Radio: the function in it goes too, Frenatura stays
    assert items[2].background(1).color().name().upper() == LINKED_BG
    assert items[1].background(1).style() == Qt.NoBrush  # not highlighted
    assert dialog.selected_button.text() == "Scarta la selezionata e 1 collegata"
    assert "Si scartano anche, perché collegate: «Creato" in dialog.note.text()
    changed = []
    dialog.changed.connect(changed.append)
    dialog.selected_button.click()
    assert names(p) == ["Frenatura", "Odometria"] and changed and radio.uuid in changed[0]
    items = dialog._items()
    dialog.list.setCurrentItem(items[2])  # the function: restored with the domain it needs
    assert dialog.selected_button.text() == "Ripristina la selezionata e 1 collegata"
    assert "Si ripristinano anche, perché le servono" in dialog.note.text()
    dialog.selected_button.click()
    assert names(p) == ["Frenatura", "Odometria", "Radio"] and not any(e.undone for e in j.entries)
