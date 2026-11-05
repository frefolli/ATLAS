"""Rami › Integra: a branch integrated into the one in use by ATLAS (not by Git): field by field, the automatic
identifiers renumbered, the sheets kept in step; branches with no version in common refused; the merges made outside
ATLAS recognized."""
import pytest
from PySide6.QtWidgets import QApplication

from arcadia_tool.storage.merge import THEIRS
from arcadia_tool.storage.project import ATLAS_MERGE, Project, Receive, made_by_atlas

AUTHOR = "Prova <prova@example.com>"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def start(tmp_path):
    p = Project.create(tmp_path / "p", "Prova")
    t1, t2, t3 = (p.new_element("team", name=n) for n in ("RFI", "FBK", "UniMiB"))
    domain = p.new_element("domain", name="Odometria")
    domain.set("team", t1.uuid)
    p.update(domain)  # the team lists it (kept in step)
    p.save()
    p.publish("v1", AUTHOR)
    return p, (t1, t2, t3), domain


def reopen(p):
    p.close()
    return Project.open(p.path)


def move(p, uuid, team):
    domain = p.model.get(uuid)
    previous = domain.copy()
    domain.set("team", team)
    p.update(domain, previous)


def test_a_branch_is_integrated_field_by_field_with_the_sheets_kept_in_step(tmp_path):
    p, (t1, t2, t3), domain = start(tmp_path)
    v1 = p.repository.head()
    p.switch_branch("att/T2", v1)
    p = reopen(p)
    move(p, domain.uuid, t2.uuid)  # the domain to FBK: FBK lists it
    p.new_element("domain", name="Radio")  # DF02 on this branch
    p.save()
    branch_head = p.publish("odometria a FBK", AUTHOR)
    p.switch_branch("master")
    p = reopen(p)
    move(p, domain.uuid, t3.uuid)  # meanwhile on master: to UniMiB
    p.new_element("domain", name="Frenatura")  # DF02 on master too
    p.save()
    p.publish("odometria a UniMiB", AUTHOR)
    receive = p.prepare_integration("att/T2", branch_head)
    assert receive.state == Receive.MERGE and receive.into == "master" and not receive.foreign
    conflict = next(c for c in receive.result.conflicts if c.field == "team")
    result = p.apply_receive(receive, {conflict.key: THEIRS}, AUTHOR)  # the choice: FBK
    assert result.resolved and result.renumbered  # one of the two DF02 renumbered
    p = reopen(p)
    teams = {t.get("name"): t for t in p.model.of_kind("team")}
    assert p.model.get(domain.uuid).get("team") == teams["FBK"].uuid
    assert domain.uuid in teams["FBK"].get("domains")
    assert domain.uuid not in (teams["UniMiB"].get("domains") or [])  # kept in step: Git would have left it
    assert domain.uuid not in (teams["RFI"].get("domains") or [])
    assert sorted(d.get("id") for d in p.model.of_kind("domain")) == ["DF01", "DF02", "DF03"]
    last = p.versions()[0]
    assert last.is_merge and made_by_atlas(last) and ATLAS_MERGE in last.message
    assert last.title == "Integrazione del ramo «att/T2» in «master» (1 versione)"
    assert p.current_branch() == "master" and not p.has_unpublished_changes()


def test_a_branch_ahead_is_taken_as_it_is_and_one_already_in_is_up_to_date(tmp_path):
    p, teams, domain = start(tmp_path)
    p.switch_branch("att/T3", p.repository.head())
    p = reopen(p)
    p.new_element("domain", name="Radio")
    p.save()
    ahead = p.publish("radio", AUTHOR)
    p.switch_branch("master")
    p = reopen(p)
    receive = p.prepare_integration("att/T3", ahead)
    assert receive.state == Receive.FAST_FORWARD
    p.apply_receive(receive, None, AUTHOR)
    p = reopen(p)
    assert p.repository.head() == ahead and p.current_branch() == "master"
    assert p.prepare_integration("att/T3", ahead).state == Receive.UP_TO_DATE
    p.new_element("domain", name="Non pubblicato")
    assert p.prepare_integration("att/T3", ahead).state == Receive.PUBLISH_FIRST


def test_branches_with_no_version_in_common_are_not_integrated(tmp_path):
    p, teams, domain = start(tmp_path)
    other, *_ = start(tmp_path / "altro")  # a project created apart
    heads = p.repository.fetch(str(other.path))
    receive = p.prepare_integration("master", heads["master"])
    assert receive.state == Receive.UNRELATED and receive.result is None


def test_a_merge_made_outside_atlas_is_recognized(tmp_path):
    p, teams, domain = start(tmp_path)
    v1 = p.repository.head()
    p.switch_branch("att/git", v1)
    p = reopen(p)
    p.new_element("domain", name="Radio")
    p.save()
    side = p.publish("radio", AUTHOR)
    p.switch_branch("master")
    p = reopen(p)
    p.new_element("domain", name="Frenatura")
    p.save()
    p.publish("frenatura", AUTHOR)
    # A merge as Git makes it (a second parent, its own message, no renumbering): then on a branch.
    git_merge = p.repository.save_version("Merge branch 'att/git' into master", AUTHOR, p._version_files(),
                                          merged=side)
    p.switch_branch("att/T1", v1)
    p = reopen(p)
    receive = p.prepare_integration("master", git_merge)
    assert [v.sha for v in receive.foreign] == [git_merge]
    assert not made_by_atlas(receive.foreign[0])


def test_the_window_of_the_branches_integrates_and_only_the_da_into_main(app, tmp_path, monkeypatch):
    from types import SimpleNamespace
    from arcadia_tool.ui import main_window as mw
    from arcadia_tool.ui.branches import BranchesDialog
    from arcadia_tool.ui.receive import ReceiveDialog

    p, (t1, t2, t3), domain = start(tmp_path)
    v1 = p.repository.head()
    p.switch_branch("att/T2", v1)
    p = reopen(p)
    p.new_element("domain", name="Radio")
    p.save()
    p.publish("radio", AUTHOR)
    p.switch_branch("master")
    p = reopen(p)
    p.new_element("domain", name="Frenatura")
    p.save()
    p.publish("frenatura", AUTHOR)
    # The Design Authority: RFI, with Anna. Mario (FBK) may not integrate into master.
    rfi = p.model.get(t1.uuid)
    rfi.set("design_authority", True)
    rfi.set("members", [{"name": "Anna Bianchi", "account": "a" * 32}])
    p.update(rfi)
    p.save()
    p.publish("DA", AUTHOR)
    mario = SimpleNamespace(id="b" * 32, full_name="Mario Rossi")
    anna = SimpleNamespace(id="a" * 32, full_name="Anna Bianchi")
    dialog = BranchesDialog(p, {}, mario)
    rows = {dialog.table.item(r, 0).text(): r for r in range(dialog.table.rowCount())}
    dialog.table.selectRow(rows["att/T2"])
    assert not dialog.integrate_button.isEnabled() and "Solo la Design Authority" in dialog.integrate_button.toolTip()
    dialog = BranchesDialog(p, {}, anna)
    dialog.table.selectRow(rows["att/T2"])
    assert dialog.integrate_button.isEnabled()
    dialog.integrate()
    assert dialog.request[:2] == ("integrate", "att/T2")
    # The main window: the window of the merge, applied; the project opened again on master.
    window = mw.MainWindow()
    window._set_project(p)
    window.open_project = lambda path, confirmed=False, alert=True: window._set_project(Project.open(path))
    window.user = SimpleNamespace(id="b" * 32, full_name="Mario Rossi", email="m@x.it", username="mario")
    assert window.branch_request(dialog.request) is None  # Mario: not into master, also from here
    window.user = SimpleNamespace(id="a" * 32, full_name="Anna Bianchi", email="a@x.it", username="anna")

    def run(d):  # the preparation in its thread, then «Ricevi» (here: Integra)
        d.start()
        d.worker.wait(20000)
        app.processEvents()
        assert d.receive.state == Receive.MERGE and "Integrazione del ramo «att/T2»" in d.windowTitle() + \
            d.findChildren(type(d.status))[0].text()
        d.apply()
        return True
    monkeypatch.setattr(ReceiveDialog, "exec", run)
    monkeypatch.setattr(mw.QMessageBox, "information", lambda *a, **k: None)
    result = window.branch_request(dialog.request)
    assert result.applied and window.project.current_branch() == "master"
    assert sorted(d.get("name") for d in window.project.model.of_kind("domain")) == ["Frenatura", "Odometria",
                                                                                     "Radio"]
    assert made_by_atlas(window.project.versions()[0])
    window._set_project(None)
    window.close()


def diverged(tmp_path):
    """master and att/T2 from v1: the domain moved to FBK on the branch, to UniMiB on master (a conflict), and a new
    domain on each side (merged by itself)."""
    p, (t1, t2, t3), domain = start(tmp_path)
    p.switch_branch("att/T2", p.repository.head())
    p = reopen(p)
    move(p, domain.uuid, t2.uuid)
    p.new_element("domain", name="Radio")
    p.save()
    branch_head = p.publish("odometria a FBK", AUTHOR)
    p.switch_branch("master")
    p = reopen(p)
    move(p, domain.uuid, t3.uuid)
    p.new_element("domain", name="Frenatura")
    p.save()
    p.publish("odometria a UniMiB", AUTHOR)
    return p, (t1, t2, t3), domain, branch_head


def test_the_window_of_the_integration_previews_the_result_and_can_be_cancelled(app, tmp_path):
    from arcadia_tool.ui.receive import ReceiveDialog

    p, (t1, t2, t3), domain, branch_head = diverged(tmp_path)
    head = p.repository.head()
    dialog = ReceiveDialog(p, {}, AUTHOR, integrate=("att/T2", branch_head))
    dialog.start()
    dialog.worker.wait(20000)
    app.processEvents()
    assert dialog.apply_button.text() == "Integra" and dialog.close_button.text() == "Annulla integrazione"
    # Merged by itself: Radio (from the branch) is in the preview; only the team of the domain is left to choose.
    assert dialog.conflicts.rowCount() == 1 and "team" in dialog.conflicts.item(0, 0).text().lower()
    names = lambda d: {e.get("name") for e in merged_domains(d)}
    assert names(dialog) == {"Odometria", "Frenatura", "Radio"}
    assert "Unite automaticamente" in dialog.conflicts_title.text() and "1 conflitto" in dialog.conflicts_title.text()
    assert not dialog.apply_button.isEnabled()
    # The choice is followed by the preview: the domain goes to FBK.
    combo = dialog.conflicts.cellWidget(0, 3)
    combo.setCurrentIndex(combo.findData(THEIRS))
    dialog._refresh_preview()
    assert next(e for e in merged_domains(dialog) if e.uuid == domain.uuid).get("team") == t2.uuid
    assert dialog.apply_button.isEnabled()
    # Annulla integrazione: nothing changes.
    dialog.reject()
    assert not dialog.applied and p.repository.head() == head and not p.has_unpublished_changes()
    assert p.model.get(domain.uuid).get("team") == t3.uuid


def merged_domains(dialog):
    from arcadia_tool.storage.merge import merged_model
    return merged_model(dialog.preview_result.files).of_kind("domain")


def test_the_branch_integrated_is_deleted_here_and_on_the_remote_with_the_next_send(tmp_path):
    from dulwich import porcelain
    from arcadia_tool.storage.project import ProjectError
    from arcadia_tool.storage.repository import remote_branches

    url = str(tmp_path / "server.git")
    porcelain.init(url, bare=True).close()
    p, (t1, t2, t3), domain, branch_head = diverged(tmp_path)
    p.repository.set_remote_url(url)
    for name in ("att/T2", "master"):  # both branches on the server
        p.switch_branch(name)
        p = reopen(p)
        p.set_local_settings(branch=name)
        p.push()
    receive = p.prepare_integration("att/T2", branch_head)
    conflict = next(c for c in receive.result.conflicts if c.field == "team")
    p.apply_receive(receive, {conflict.key: THEIRS}, AUTHOR)
    p = reopen(p)
    with pytest.raises(ProjectError):
        p.delete_integrated_branch("master")  # the branch in use
    assert p.delete_integrated_branch("att/T2")
    assert "att/T2" not in p.repository.local_heads() and p.branches_to_delete() == ["att/T2"]
    assert "att/T2" not in [b.name for b in p.branches()]  # gone already, also before the send
    assert "att/T2" in remote_branches(url)
    p.push()
    assert p.deleted_branches == ["att/T2"] and not p.branches_to_delete()
    assert set(remote_branches(url)) == {"master"}


def test_a_branch_with_versions_sent_meanwhile_is_not_deleted_from_the_remote(tmp_path):
    from dulwich import porcelain
    from arcadia_tool.storage.project import clone_project
    from arcadia_tool.storage.repository import remote_branches

    url = str(tmp_path / "server.git")
    porcelain.init(url, bare=True).close()
    p, teams, domain = start(tmp_path)
    p.repository.set_remote_url(url)
    p.set_local_settings(branch="master")
    p.push()
    p.switch_branch("att/T3", p.repository.head())
    p = reopen(p)
    p.set_local_settings(branch="att/T3")
    p.new_element("domain", name="Radio")
    p.save()
    ahead = p.publish("radio", AUTHOR)
    p.push()
    p.switch_branch("master")
    p = reopen(p)
    p.set_local_settings(branch="master")
    p.apply_receive(p.prepare_integration("att/T3", ahead), None, AUTHOR)
    p = reopen(p)
    assert p.delete_integrated_branch("att/T3")
    # Meanwhile a colleague sends a version to att/T3: it is not integrated, the branch stays on the server.
    colleague = Project.open(clone_project(url, tmp_path / "collega"))
    colleague.switch_branch("att/T3")
    colleague = reopen(colleague)
    colleague.set_local_settings(branch="att/T3")
    colleague.new_element("domain", name="Frenatura")
    colleague.save()
    colleague.publish("frenatura", AUTHOR)
    colleague.push()
    p.repository.set_remote_heads(p.repository.fetch(url))
    p.push()
    assert p.kept_branches == ["att/T3"] and not p.deleted_branches
    assert set(remote_branches(url)) == {"master", "att/T3"} and not p.branches_to_delete()
    colleague.close()


def test_only_the_design_authority_merges_into_the_main_branch_also_when_receiving(app, tmp_path):
    from types import SimpleNamespace
    from dulwich import porcelain
    from arcadia_tool.storage.project import clone_project
    from arcadia_tool.storage.repository import remote_branches
    from arcadia_tool.ui.receive import ReceiveDialog

    url = str(tmp_path / "server.git")
    porcelain.init(url, bare=True).close()
    first, (rfi, *_), domain = start(tmp_path)
    da = first.model.get(rfi.uuid)
    da.set("design_authority", True)
    da.set("members", [{"name": "Anna Bianchi", "account": "a" * 32}])
    first.update(da)
    first.save()
    first.publish("DA", AUTHOR)
    first.repository.set_remote_url(url)
    first.set_local_settings(branch="master")
    first.push()
    first.close()
    mario = SimpleNamespace(id="b" * 32, full_name="Mario Rossi")
    anna = SimpleNamespace(id="a" * 32, full_name="Anna Bianchi")
    mine, colleague = (Project.open(clone_project(url, tmp_path / n)) for n in ("mario", "collega"))
    colleague.new_element("domain", name="Frenatura")
    colleague.save()
    colleague.publish("frenatura", AUTHOR)
    colleague.push()
    mine.new_element("domain", name="Radio")
    mine.save()
    mine.publish("radio", AUTHOR)
    assert mine.main_denied(anna) is None and "Solo la Design Authority" in mine.main_denied(mario)

    def receive_as(user):
        dialog = ReceiveDialog(mine, {}, AUTHOR, user=user)
        dialog.start()
        dialog.worker.wait(20000)
        app.processEvents()
        assert dialog.receive.state == Receive.MERGE
        return dialog

    dialog = receive_as(mario)  # Mario, of a team: not merged on master
    assert "Solo la Design Authority" in dialog.status.text()
    assert dialog.apply_button.isHidden() and not dialog.move_button.isHidden()
    head = mine.repository.head()
    dialog.apply()
    assert not dialog.applied and mine.repository.head() == head
    assert not receive_as(anna).apply_button.isHidden()  # Anna, of the DA: the merge is offered
    # Sposta le mie versioni su un nuovo ramo: «radio» on att/mario, to send; master back as on the server.
    mine.move_unsent_to_branch("att/mario")
    mine.close()
    mine = Project.open(mine.path)
    assert mine.current_branch() == "att/mario" and mine.repository.head() == head
    assert mine.repository.local_heads()["master"] == mine.repository.remote_branch_head("master")
    assert [v.title for v in mine.unsent_versions()] == ["radio"]
    mine.push()
    assert set(remote_branches(url)) == {"master", "att/mario"}
    mine.close()
    colleague.close()


def test_on_the_main_branch_a_team_member_publishes_and_sends_only_on_a_new_branch(app, tmp_path, monkeypatch):
    from types import SimpleNamespace
    from dulwich import porcelain
    from arcadia_tool.storage.repository import remote_branches
    from arcadia_tool.ui import main_window as mw
    from arcadia_tool.ui.versions import PublishDialog

    url = str(tmp_path / "server.git")
    porcelain.init(url, bare=True).close()
    p, (rfi, *_), domain = start(tmp_path)
    da = p.model.get(rfi.uuid)
    da.set("design_authority", True)
    da.set("members", [{"name": "Anna Bianchi", "account": "a" * 32}])
    p.update(da)
    p.save()
    p.publish("DA", AUTHOR)
    p.repository.set_remote_url(url)
    p.set_local_settings(branch="master")
    p.push()
    mario = SimpleNamespace(id="b" * 32, full_name="Mario Rossi", email="m@x.it", username="mario")
    anna = SimpleNamespace(id="a" * 32, full_name="Anna Bianchi", email="a@x.it", username="anna")
    p.new_element("domain", name="Radio")
    p.save()
    dialog = PublishDialog(p, user=mario)  # Pubblica: on master only the DA; Mario on a new branch
    assert not dialog.on_current.isEnabled() and dialog.on_new.isChecked() and dialog.denied
    dialog = PublishDialog(p, user=anna)
    assert dialog.on_current.isEnabled() and dialog.on_current.isChecked() and not dialog.denied
    # Versions published on master before (e.g. by an older ATLAS): Invia moves them to a new branch first.
    p.publish("radio", AUTHOR)
    window = mw.MainWindow()
    window.user = mario
    window._set_project(p)
    monkeypatch.setattr(mw.QMessageBox, "question", lambda *a, **k: mw.QMessageBox.Yes)
    monkeypatch.setattr("PySide6.QtWidgets.QInputDialog.getText", lambda *a, **k: ("att/mario", True))
    monkeypatch.setattr(mw.PushDialog, "exec", lambda d: d.project.push())
    window.send_versions()
    assert window.project.current_branch() == "att/mario"
    assert set(remote_branches(url)) == {"master", "att/mario"}
    repository = window.project.repository  # master as on the server: the version is only on att/mario
    assert repository.local_heads()["master"] == repository.remote_branch_head("master") != repository.head()
    window._set_project(None)
    window.close()
