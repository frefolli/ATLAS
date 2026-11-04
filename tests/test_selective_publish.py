"""«Pubblica» of some of the changes only: the changes depend on one another through their references, and a version
never refers to an element it does not have; what is not published stays as a local change."""
from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from arcadia_tool.model import discussions as d
from arcadia_tool.storage.project import Project
from arcadia_tool.storage.selective import dependencies, dependents, required

AUTHOR = "Prova <prova@example.com>"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def project(tmp_path):
    p = Project.create(tmp_path / "p", "Prova")
    old = p.new_element("domain", name="Odometria")
    kept = p.new_element("domain", name="Frenatura")
    p.save()
    p.publish("v1", AUTHOR)
    return p, old, kept


def published_names(p):
    return sorted(e.get("name") for e in p.published_model().of_kind("domain", "system_function") if e.get("name"))


def test_the_changes_needed_by_a_change_and_those_that_need_it(tmp_path):
    p, old, kept = project(tmp_path)
    new = p.new_element("domain", name="Radio")
    sf = p.new_element("system_function", name="Stabilire la sessione", domain=new.uuid)
    moved = p.new_element("system_function", name="Frenare", domain=kept.uuid)
    p.save()
    p.publish("v2", AUTHOR)
    moved.set("domain", new.uuid)  # it moves to the domain removed below… and back
    moved.set("domain", old.uuid)
    p.update(moved)
    p.delete_element(kept.uuid)  # removed: the function that referred to it changes with it
    changed = [new.uuid, sf.uuid, moved.uuid, kept.uuid]
    needs = dependencies(p.published_model(), p.model, changed)
    assert needs[kept.uuid] == {moved.uuid} and not needs[moved.uuid]
    assert required(needs, [kept.uuid]) == {kept.uuid, moved.uuid}
    assert dependents(needs, [moved.uuid]) == {moved.uuid, kept.uuid}
    # In v2 the domain and the function were new together: the function needs the domain.
    p2, old2, _kept2 = project(tmp_path / "secondo")
    radio = p2.new_element("domain", name="Radio")
    session = p2.new_element("system_function", name="Stabilire la sessione", domain=radio.uuid)
    needs = dependencies(p2.published_model(), p2.model, [radio.uuid, session.uuid])
    assert needs == {radio.uuid: set(), session.uuid: {radio.uuid}}
    assert dependents(needs, [radio.uuid]) == {radio.uuid, session.uuid}


def test_only_the_changes_chosen_are_published_the_others_stay_local(tmp_path):
    p, old, kept = project(tmp_path)
    radio = p.new_element("domain", name="Radio")
    session = p.new_element("system_function", name="Stabilire la sessione", domain=radio.uuid)
    old.set("name", "Odometria e localizzazione")
    p.update(old)
    p.publish("solo la rinomina", AUTHOR, only={old.uuid})
    assert published_names(p) == ["Frenatura", "Odometria e localizzazione"]
    assert p.has_unpublished_changes() and sorted(p.changed_elements()) == sorted([radio.uuid, session.uuid])
    reopened = Project.open(p.path)  # still on disk, to publish later
    assert reopened.model.get(session.uuid) is not None
    reopened.publish("il resto", AUTHOR)
    assert published_names(reopened) == ["Frenatura", "Odometria e localizzazione", "Radio",
                                         "Stabilire la sessione"]
    assert not reopened.has_unpublished_changes()


def test_the_files_attached_and_the_settings_follow_what_is_published(tmp_path):
    p, old, kept = project(tmp_path)
    p.new_element("team", name="RFI", members=[{"name": "Anna", "account": "a" * 32}])
    adr = p.new_element("adr", title="Una decisione", adr_type="Altro / decisione trasversale", status="Proposta")
    p.save()
    p.publish("v2", AUTHOR)
    anna = SimpleNamespace(id="a" * 32, full_name="Anna")
    message = d.post(p, adr, anna, "Con un allegato", files=[("schema.png", b"PNG")])
    (p.path / "project.yaml").write_text((p.path / "project.yaml").read_text(encoding="utf-8") +
                                         "# cambiata\n", encoding="utf-8")
    assert p.settings_unpublished()
    other = p.new_element("domain", name="Radio")
    p.publish("solo il dominio, senza le impostazioni", AUTHOR, only={other.uuid}, settings=False)
    files = p.repository.files_at(p.repository.head())
    assert not any(f.startswith("assets/") for f in files)  # the message is not published: nor its file
    assert b"# cambiata" not in files["project.yaml"] and p.settings_unpublished()
    p.publish("il messaggio", AUTHOR, only={message.uuid})
    files = p.repository.files_at(p.repository.head())
    assert files[message.get("attachments")[0]] == b"PNG" and b"# cambiata" in files["project.yaml"]


def test_the_window_publish_ticks_the_changes_with_their_dependencies(app, tmp_path):
    from arcadia_tool.ui.versions import PublishDialog

    p, old, kept = project(tmp_path)
    radio = p.new_element("domain", name="Radio")
    session = p.new_element("system_function", name="Stabilire la sessione", domain=radio.uuid)
    old.set("name", "Odometria e localizzazione")
    p.update(old)
    dialog = PublishDialog(p)
    assert dialog.windowFlags() & Qt.WindowMaximizeButtonHint  # the window can be maximized
    view = dialog.view
    assert view.chosen == {radio.uuid, session.uuid, old.uuid}
    assert dialog.chosen() == (None, True)  # everything: as before
    items = {}
    for i in range(view.tree.topLevelItemCount()):
        group = view.tree.topLevelItem(i)
        for j in range(group.childCount()):
            change = group.child(j).data(0, 0x0100)
            items[change.uuid] = group.child(j)
    items[radio.uuid].setCheckState(0, Qt.Unchecked)  # the domain left out: the function that needs it too
    assert view.chosen == {old.uuid} and items[session.uuid].checkState(0) == Qt.Unchecked
    assert "Escluse anche, perché ne dipendono: " in view.note.text() and "Stabilire la sessione" in view.note.text()
    assert dialog.chosen() == ({old.uuid}, True)
    assert "Da pubblicare: 1 di 3 modifiche · 2 restano locali" in dialog.chosen_label.text()
    items[session.uuid].setCheckState(0, Qt.Checked)  # the function chosen: the domain it needs too
    assert view.chosen == {old.uuid, radio.uuid, session.uuid}
    assert "Selezionate anche, perché servono: DF03 Radio" in view.note.text()
    items[radio.uuid].setCheckState(0, Qt.Unchecked)
    dialog.message.setPlainText("Solo la rinomina")
    dialog.author_name.setText("Prova")
    dialog.author_email.setText("prova@example.com")
    dialog._publish()
    assert dialog.sha and published_names(p) == ["Frenatura", "Odometria e localizzazione"]
    assert sorted(p.changed_elements()) == sorted([radio.uuid, session.uuid])
