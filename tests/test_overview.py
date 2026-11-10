"""«Vista d'insieme»: what the branches propose over the main branch, computed without writing anything."""
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from arcadia_tool.storage.overview import (APPROVED, CHANGED, DIVERGENT, NEW, REMOVED, OverviewBuilder, Source)
from arcadia_tool.storage.project import Project

AUTHOR = "Prova <prova@example.com>"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def reopen(p):
    p.close()
    return Project.open(p.path)


def start(tmp_path):
    p = Project.create(tmp_path / "p", "Prova")
    domains = {n: p.new_element("domain", name=n) for n in ("Odometria", "Radio", "Frenatura", "Balise")}
    p.save()
    p.publish("v1", AUTHOR)
    return p, domains


def on_branch(p, name, change, base=None):
    p.switch_branch(name, base or p.repository.head())
    p = reopen(p)
    change(p)
    p.save()
    p.publish(f"lavoro su {name}", AUTHOR)
    p.switch_branch("master")
    return reopen(p)


def rename(p, uuid, name):
    e = p.model.get(uuid)
    previous = e.copy()
    e.set("name", name)
    p.update(e, previous)


def view(p, *names):
    main, sources = p.overview_sources()
    return OverviewBuilder(p.repository).build(main, [s for s in sources if not names or s.name in names])


def test_each_element_says_where_it_stands(tmp_path):
    p, d = start(tmp_path)
    new = {}

    def a(q):
        rename(q, d["Odometria"].uuid, "Odometria A")
        rename(q, d["Radio"].uuid, "Radio A")
        new["a"] = q.new_element("domain", name="Solo A")
        q.delete_element(d["Balise"].uuid)

    def b(q):
        rename(q, d["Radio"].uuid, "Radio B")

    p = on_branch(p, "att/A", a)
    p = on_branch(p, "att/B", b)
    o = view(p)
    state = {u: e.state for u, e in o.entries.items()}
    assert state[d["Frenatura"].uuid] == APPROVED
    assert state[d["Odometria"].uuid] == CHANGED and o.entries[d["Odometria"].uuid].branches == ["att/A"]
    assert state[new["a"].uuid] == NEW and state[d["Balise"].uuid] == REMOVED
    radio = o.entries[d["Radio"].uuid]
    assert radio.state == DIVERGENT and radio.divergent_fields == ["name"]
    assert {pr.branch: pr.fields["name"] for pr in radio.proposals} == {"att/A": "Radio A", "att/B": "Radio B"}
    assert radio.approved.get("name") == "Radio"
    only_b = view(p, "att/B")  # the branches chosen only
    assert only_b.entries[d["Radio"].uuid].state == CHANGED and new["a"].uuid not in only_b.entries
    assert only_b.entries[d["Odometria"].uuid].state == APPROVED


def test_a_branch_left_behind_does_not_propose_the_old_values(tmp_path):
    p, d = start(tmp_path)
    p = on_branch(p, "att/A", lambda q: rename(q, d["Odometria"].uuid, "Odometria A"))
    rename(p, d["Radio"].uuid, "Radio approvata")  # on master, after the branch left
    p.save()
    p.publish("master va avanti", AUTHOR)
    o = view(p)
    assert o.entries[d["Radio"].uuid].state == APPROVED and o.entries[d["Radio"].uuid].approved.get("name") == "Radio approvata"
    assert o.entries[d["Odometria"].uuid].state == CHANGED


def test_references_propose_only_what_the_branch_added_or_removed(tmp_path):
    p = Project.create(tmp_path / "p", "Prova")
    team = p.new_element("team", name="RFI")
    d1, d2, d3 = (p.new_element("domain", name=n) for n in "ABC")
    team.set("domains", [d1.uuid])
    p.save()
    p.publish("v1", AUTHOR)

    def add(q, uuid):
        e = q.model.get(team.uuid)
        previous = e.copy()
        e.set("domains", [*(e.get("domains") or []), uuid])
        q.update(e, previous)

    p = on_branch(p, "att/A", lambda q: add(q, d2.uuid))
    add(p, d3.uuid)  # on master, after the branch left
    p.save()
    p.publish("master", AUTHOR)
    entry = view(p).entries[team.uuid]
    assert entry.state == CHANGED and set(entry.proposals[0].fields["domains"]) >= {d1.uuid, d2.uuid, d3.uuid}


def test_what_is_integrated_becomes_approved(tmp_path):
    p, d = start(tmp_path)
    p = on_branch(p, "att/A", lambda q: rename(q, d["Odometria"].uuid, "Odometria A"))
    assert view(p).entries[d["Odometria"].uuid].state == CHANGED
    main, sources = p.overview_sources()
    receive = p.prepare_integration("att/A", sources[0].sha)
    p.apply_receive(receive, {}, AUTHOR)
    p = reopen(p)
    entry = view(p).entries[d["Odometria"].uuid]
    assert entry.state == APPROVED and entry.approved.get("name") == "Odometria A"


def test_two_branches_with_the_same_number_stay_distinct(tmp_path, app):
    from arcadia_tool.ui.overview import row_text

    p, d = start(tmp_path)
    made = {}
    p = on_branch(p, "att/A", lambda q: made.__setitem__("a", q.new_element("adr", title="Decisione A")))
    p = on_branch(p, "att/B", lambda q: made.__setitem__("b", q.new_element("adr", title="Decisione B")),
                  base=p.overview_sources()[0].sha)
    o = view(p)
    a, b = o.entries[made["a"].uuid], o.entries[made["b"].uuid]
    assert a.element.get("id") == b.element.get("id")
    assert a.state == b.state == NEW
    assert row_text(o, a).startswith(f"{a.element.get('id')} · att/A") and "att/B" in row_text(o, b)


def test_a_branch_with_nothing_in_common_is_excluded(tmp_path):
    p, d = start(tmp_path)

    class Repo:
        def __getattr__(self, name):
            return getattr(p.repository, name)

        def merge_base(self, a, b):
            return None

    main = Source("master", p.repository.head())
    o = OverviewBuilder(Repo()).build(main, [Source("altro", p.repository.head())])
    assert not o.branches and o.excluded[0][0].name == "altro"
    assert all(e.state == APPROVED for e in o.entries.values())


def test_the_view_writes_nothing(tmp_path, app):
    from arcadia_tool.ui.overview import OverviewSetup, OverviewWindow

    p, d = start(tmp_path)
    p = on_branch(p, "att/A", lambda q: rename(q, d["Odometria"].uuid, "Odometria A"))
    head, heads = p.repository.head(), p.repository.local_heads()
    model_files = {f: f.read_bytes() for f in (p.path / "model").rglob("*.yaml")}
    setup = OverviewSetup(p)
    setup.worker.wait(20000)
    app.processEvents()
    setup.create()
    window = OverviewWindow(setup.overview, setup.shown())
    assert window._items
    assert p.repository.head() == head and p.repository.local_heads() == heads
    assert {f: f.read_bytes() for f in (p.path / "model").rglob("*.yaml")} == model_files
    assert not p.has_unpublished_changes()
    window.close()


def wait(setup, app):
    setup.worker.wait(20000)
    app.processEvents()


def test_the_setup_chooses_branches_and_elements_and_remembers(tmp_path, app):
    from arcadia_tool.ui.overview import OverviewSetup

    p, d = start(tmp_path)
    p = on_branch(p, "att/A", lambda q: rename(q, d["Odometria"].uuid, "Odometria A"))
    p = on_branch(p, "att/B", lambda q: q.new_element("adr", title="Decisione B"))
    setup = OverviewSetup(p)
    wait(setup, app)
    assert setup.branch_list.count() == 2 and setup.overview.entries[d["Odometria"].uuid].state == CHANGED
    setup.choose_pending()
    shown = setup.shown()
    assert d["Odometria"].uuid in shown and d["Radio"].uuid not in shown
    setup.choose_adrs()
    assert all(setup.overview.entries[u].kind == "adr" for u in setup.shown()) and setup.shown()
    setup.choose_all()
    assert d["Radio"].uuid in setup.shown()
    setup.branch_list.item(0).setCheckState(Qt.Unchecked)  # att/A out
    assert setup.overview.entries[d["Odometria"].uuid].state == APPROVED
    setup.create()
    again = OverviewSetup(p)
    wait(again, app)
    assert again.branch_list.item(0).checkState() == Qt.Unchecked and again.branch_list.item(1).checkState() == Qt.Checked


def test_the_elements_linked_are_added_only_if_asked(tmp_path, app):
    from arcadia_tool.ui.overview import OverviewSetup

    p = Project.create(tmp_path / "p", "Prova")
    team = p.new_element("team", name="RFI")
    domain = p.new_element("domain", name="Radio")
    domain.set("team", team.uuid)
    p.update(domain)
    p.save()
    p.publish("v1", AUTHOR)
    setup = OverviewSetup(p)
    wait(setup, app)
    setup._tick(lambda kind, entry: kind == "domain")
    assert team.uuid not in setup.shown()
    setup.linked.setChecked(True)
    assert team.uuid in setup.shown()


def test_the_window_filters_and_shows_approved_and_proposed_values(tmp_path, app):
    from arcadia_tool.ui.overview import OverviewWindow, entry_html

    p, d = start(tmp_path)
    p = on_branch(p, "att/A", lambda q: rename(q, d["Odometria"].uuid, "Odometria A"))
    o = view(p)
    window = OverviewWindow(o, set(o.entries))
    html = entry_html(o, o.entries[d["Odometria"].uuid], set(o.entries))
    assert "Approvato (master)" in html and "att/A" in html
    window.tree.setCurrentItem(window._items[d["Odometria"].uuid])
    assert "att/A" in window.sheet.toPlainText()
    window.state_boxes[APPROVED].setChecked(False)
    assert window._items[d["Radio"].uuid].isHidden() and not window._items[d["Odometria"].uuid].isHidden()
    window.search.setText("nessun risultato")
    assert window._items[d["Odometria"].uuid].isHidden()
    window.close()


def test_the_discussion_of_an_adr_comes_from_all_the_branches(tmp_path, app):
    from arcadia_tool.ui.overview import entry_html

    p, d = start(tmp_path)
    adr = p.new_element("adr", title="Decisione")
    p.save()
    p.publish("adr", AUTHOR)

    def write(q):
        q.new_element("message", subject=adr.uuid, author="Mario", text="Sono d'accordo", posted="2026-11-09T10:00:00")

    p = on_branch(p, "att/A", write)
    o = view(p)
    html = entry_html(o, o.entries[adr.uuid], set(o.entries))
    assert "Discussione" in html and "accordo" in html and "att/A" in html
    assert all(e.kind != "message" for e in o.shown())


def test_the_button_of_the_view_is_in_the_top_bar(tmp_path, app, monkeypatch):
    from PySide6.QtWidgets import QToolBar

    from arcadia_tool.ui import main_window as mw

    p, d = start(tmp_path)
    window = mw.MainWindow()
    assert not window.overview_action.isEnabled()
    window._set_project(p)
    assert window.overview_action.isEnabled()
    assert window.overview_action in window.findChild(QToolBar).actions()

    class Setup:
        overview = view(p)

        def __init__(self, *a):
            pass

        def exec(self):
            return mw.QDialog.Accepted

        def shown(self):
            return set(Setup.overview.entries)

    monkeypatch.setattr(mw, "OverviewSetup", Setup)
    window.open_overview()
    assert window.overview_window is not None and window.overview_window.isVisible()
    window._set_project(None)  # the project goes, the view with it
    assert window.overview_window is None
    window.close()


def test_an_empty_main_next_to_master_is_not_the_base(tmp_path):
    from dulwich.objects import Commit, Tree

    p, d = start(tmp_path)
    repo = p.repository._repo
    tree = Tree()
    repo.object_store.add_object(tree)
    commit = Commit()
    commit.tree, commit.parents, commit.message = tree.id, [], b"Initial commit"
    commit.author = commit.committer = b"Server <server@example.com>"
    commit.author_time = commit.commit_time = 1
    commit.author_timezone = commit.commit_timezone = 0
    repo.object_store.add_object(commit)
    repo.refs[b"refs/remotes/origin/main"] = commit.id  # what a Git server creates with a new repository
    assert p.main_branch() == "master"  # the empty «main» is not the main branch
    main, sources = p.overview_sources()
    assert main.name == "master" and all(s.name != "main" for s in sources)


def test_an_element_renumbered_by_the_integration_is_approved(tmp_path):
    p, d = start(tmp_path)
    made = {}
    p = on_branch(p, "att/A", lambda q: made.__setitem__("a", q.new_element("adr", title="Dal ramo")))
    p.new_element("adr", title="Da master")
    p.save()
    p.publish("master", AUTHOR)
    main, sources = p.overview_sources()
    receive = p.prepare_integration("att/A", sources[0].sha)
    receive.only = {made["a"].uuid}
    assert p.apply_receive(receive, None, AUTHOR).renumbered
    p = reopen(p)
    assert view(p).entries[made["a"].uuid].state == APPROVED


def test_the_main_branch_set_in_the_settings_counts_ahead_and_behind(tmp_path, app):
    from types import SimpleNamespace

    from arcadia_tool.ui.branches import BranchesDialog
    from arcadia_tool.ui.project_settings import ProjectSettingsDialog

    p, d = start(tmp_path)
    p = on_branch(p, "sviluppo", lambda q: rename(q, d["Radio"].uuid, "Radio S"))
    p = on_branch(p, "att/A", lambda q: rename(q, d["Odometria"].uuid, "Odometria A"))
    rename(p, d["Frenatura"].uuid, "Frenatura M")
    p.save()
    p.publish("master va avanti", AUTHOR)
    by_name = {b.name: b for b in p.branches()}
    assert p.main_branch() == "master" and (by_name["att/A"].ahead, by_name["att/A"].behind) == (1, 1)
    p.update_settings(main_branch="sviluppo")  # chosen in the settings
    by_name = {b.name: b for b in p.branches()}
    assert p.main_branch() == "sviluppo" and by_name["sviluppo"].main
    assert (by_name["att/A"].ahead, by_name["att/A"].behind) == (1, 1) and (by_name["master"].ahead, by_name["master"].behind) == (1, 1)
    dialog = BranchesDialog(p, {}, None)
    row = next(r for r in range(dialog.table.rowCount()) if dialog.table.item(r, 0).text().startswith("att/A"))
    assert dialog.table.horizontalHeaderItem(4).text() == "Rispetto a «sviluppo»"
    assert dialog.table.item(row, 4).text() == "1 avanti, 1 indietro"
    # The choice: only the Design Authority, once it has members.
    rfi = p.new_element("team", name="RFI")
    rfi.set("design_authority", True)
    rfi.set("members", [{"name": "Anna", "account": "a" * 32}])
    p.update(rfi)
    from arcadia_tool.ui.accounts import GitAccess

    def account(ident, name):  # no server access stored: the settings only read it
        return SimpleNamespace(id=ident, full_name=name, email=f"{name}@x.it", username=name.lower(),
                               git_access=lambda host: GitAccess())

    anna, mario = account("a" * 32, "Anna"), account("b" * 32, "Mario")
    assert not ProjectSettingsDialog(p, mario).main_branch.isEnabled()
    settings = ProjectSettingsDialog(p, anna)
    assert settings.main_branch.isEnabled() and settings.main_branch.currentData() == "sviluppo"
    settings.main_branch.setCurrentIndex(0)  # automatic
    settings._save()
    assert "main_branch" not in p.settings and p.main_branch() == "master"


def test_a_branch_with_nothing_in_common_says_so(tmp_path, app):
    from dulwich.objects import Commit, Tree

    p, d = start(tmp_path)
    repo = p.repository._repo
    tree = Tree()
    repo.object_store.add_object(tree)
    commit = Commit()
    commit.tree, commit.parents, commit.message = tree.id, [], b"altro progetto"
    commit.author = commit.committer = b"Server <server@example.com>"
    commit.author_time = commit.commit_time = 1
    commit.author_timezone = commit.commit_timezone = 0
    repo.object_store.add_object(commit)
    repo.refs[b"refs/remotes/origin/altro"] = commit.id
    other = next(b for b in p.branches() if b.name == "altro")
    assert other.unrelated and other.ahead is None

