"""The discussion of an ADR or of a CQ: the messages of the members of the teams, with their files attached."""
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication

from arcadia_tool.model import discussions as d
from arcadia_tool.model.schema import ADR_SECTION
from arcadia_tool.storage.project import Project

ANNA, MARIO, LUCA = "a" * 32, "b" * 32, "c" * 32


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def user(account, name):
    return SimpleNamespace(id=account, full_name=name)


def project(tmp_path):
    p = Project.create(tmp_path / "p", "Prova")
    da = p.new_element("team", name="RFI", design_authority=True, members=[{"name": "Anna Bianchi", "account": ANNA}])
    t2 = p.new_element("team", name="Odometria", members=[{"name": "Mario Rossi", "account": MARIO},
                                                          {"name": "Anna Bianchi", "account": ANNA}])
    adr = p.new_element("adr", title="Riallocazione", adr_type=ADR_SECTION, status="Proposta")
    cq = p.new_element("clarification", problem="Cosa si intende?", status="Aperta")
    p.save()
    return p, da, t2, adr, cq


def test_the_members_write_in_the_discussion_and_the_others_see_what_is_new(tmp_path):
    p, da, t2, adr, cq = project(tmp_path)
    anna, mario = user(ANNA, "Anna Bianchi"), user(MARIO, "Mario Rossi")
    first = d.post(p, adr, mario, "  Perché proprio DF01?  ", files=[("schema.png", b"PNG"), ("nota.txt", b"x")])
    assert first.get("author") == "Mario Rossi" and first.get("team") == t2.uuid and first.get("text") == \
        "Perché proprio DF01?"
    assert first.get("attachments") == [f"assets/discussions/{first.uuid}/schema.png",
                                        f"assets/discussions/{first.uuid}/nota.txt"]
    answer = d.post(p, adr, anna, "Per la validazione dei messaggi.", team=da, reply_to=first)
    assert answer.get("team") == da.uuid and answer.get("reply_to") == first.uuid
    p.save()
    reopened = Project.open(p.path)  # each message a file of its own, the files attached in the project
    assert [m.get("text") for m in d.messages_of(reopened.model, adr.uuid)] == ["Perché proprio DF01?",
                                                                                "Per la validazione dei messaggi."]
    assert (p.path / first.get("attachments")[0]).read_bytes() == b"PNG"
    assert reopened.asset_data(first.get("attachments")[1]) == b"x"
    # New: the messages of the others not seen yet on this PC (not by time: one may arrive later).
    assert d.unread_count(reopened, adr, anna) == 1 and d.unread_count(reopened, adr, mario) == 1
    d.mark_read(reopened, adr)
    assert d.unread_count(reopened, adr, anna) == 0 and d.unread_count(reopened, cq, anna) == 0
    late = d.post(reopened, adr, mario, "Scritto prima, ricevuto dopo")
    late.set("posted", "2000-01-01T00:00:00")
    assert d.unread_count(reopened, adr, anna) == 1
    # Who writes: the members of the teams, while the discussion is open.
    assert d.write_denied(reopened.model, adr, user("d" * 32, "Estraneo")) and \
        d.write_denied(reopened.model, adr, mario) is None


def test_the_author_changes_or_deletes_and_the_da_hides(tmp_path):
    p, da, t2, adr, cq = project(tmp_path)
    anna, mario = user(ANNA, "Anna Bianchi"), user(MARIO, "Mario Rossi")
    message = d.post(p, cq, mario, "Prima versione", files=[("bozza.docx", b"DOC")])
    p.save()
    path = p.path / message.get("attachments")[0]
    assert path.exists()
    assert d.may_change(p.model, message, mario) and not d.may_change(p.model, message, anna)
    d.edit(p, message, "Seconda versione")
    assert message.get("text") == "Seconda versione" and message.get("edited")
    assert d.may_hide(p.model, anna) and not d.may_hide(p.model, mario)
    d.set_hidden(p, message, True)
    assert message.get("hidden_by_da")
    d.delete(p, message)
    p.save()
    assert message.get("deleted") and not message.get("text") and not message.get("attachments")
    assert not path.exists()  # the file attached goes with the text
    assert p.model.get(message.uuid) is message and not d.may_change(p.model, message, mario)


def test_the_discussion_closes_with_the_approval_of_the_da_and_goes_with_its_sheet(tmp_path):
    p, da, t2, adr, cq = project(tmp_path)
    mario = user(MARIO, "Mario Rossi")
    message = d.post(p, adr, mario, "Una domanda")
    assert d.closed(p.model, adr) is None
    adr.set("da_decision", "Commenti DA")
    assert d.closed(p.model, adr) is None  # comments of the DA: still open
    adr.set("da_decision", "Accolta")
    assert "approvata dalla Design Authority" in d.write_denied(p.model, adr, mario)
    assert not d.may_change(p.model, message, mario)
    cq.set("status", "Chiusa")
    assert "chiusa" in d.closed(p.model, cq)
    p.save()
    p.delete_element(adr.uuid)  # its discussion goes with it
    assert p.model.get(message.uuid) is None
    p.save()
    assert not list((p.path / "model" / "x" / "discussions").glob("*.yaml"))


def test_two_messages_written_at_the_same_time_on_two_branches_are_both_kept(tmp_path):
    from arcadia_tool.storage.merge import merge_files

    p, da, t2, adr, cq = project(tmp_path)
    base = p._version_files()
    d.post(p, adr, user(MARIO, "Mario Rossi"), "Dal ramo di Mario")
    p.save()
    ours = p._version_files()
    for f in [f for f in ours if f not in base]:
        (p.path / f).unlink()
    other = Project.open(p.path)
    d.post(other, adr, user(ANNA, "Anna Bianchi"), "Dal ramo di Anna")
    other.save()
    theirs = other._version_files()
    result = merge_files(base, ours, theirs)
    assert result.resolved and not result.conflicts
    messages = [f for f in result.files if f.startswith("model/x/discussions/")]
    assert len(messages) == 2


def test_the_sheet_of_an_adr_shows_its_discussion_and_writes_in_it(app, tmp_path, monkeypatch):
    from arcadia_tool.ui import discussion as ui
    from arcadia_tool.ui.element_editor import DISCUSSION, ElementEditor

    p, da, t2, adr, cq = project(tmp_path)
    mario, anna = user(MARIO, "Mario Rossi"), user(ANNA, "Anna Bianchi")
    first = d.post(p, adr, mario, "Una domanda di Mario")
    p.save()
    editor = ElementEditor()
    editor.user_of = lambda: anna
    changed = []
    editor.discussion_changed.connect(lambda: changed.append(True))
    editor.edit(p, adr)  # a read-only sheet: the discussion works anyway
    card = editor.widgets[DISCUSSION]
    assert card.new == {first.uuid} and d.unread_count(p, adr, anna) == 0  # shown: read
    assert card.isEnabled() and card.property("keepEnabled")
    app.processEvents()
    assert changed  # the tree is told that the messages were read
    assert card.team.count() == 2  # Anna is in two teams: she chooses the one she writes for
    card.answer(first)
    assert "In risposta a Mario Rossi" in card.replying.text()
    attached = tmp_path / "figura.png"
    attached.write_bytes(b"PNG")
    card.attach([str(attached)])
    card.text.setPlainText("La risposta di Anna")
    sent = card.send()
    assert sent.get("reply_to") == first.uuid and sent.get("attachments")
    assert sent.uuid not in p.pending() and not p.is_modified  # saved at once, on its own
    card = editor.widgets[DISCUSSION]  # the sheet shows the discussion again
    assert len(d.messages_of(p.model, adr)) == 2 and sent.uuid not in card.published
    path = sent.get("attachments")[0]
    target = tmp_path / "copia.png"
    assert card.save_attachment(path, str(target)) == str(target) and target.read_bytes() == b"PNG"
    opened = []
    monkeypatch.setattr(ui.QDesktopServices, "openUrl", lambda url: opened.append(url.toLocalFile()))
    assert card.open_attachment(path).read_bytes() == b"PNG" and opened
    # A draft of the sheet is not saved with a message.
    editor.start_editing()
    editor.widgets["title"].setText("Titolo cambiato")
    editor.flush()
    card = editor.widgets[DISCUSSION]
    card.text.setPlainText("Un altro messaggio")
    card.send()
    assert adr.get("title") == "Riallocazione" and editor.dirty
    assert editor.draft.get("title") == "Titolo cambiato"
    editor.cancel_changes(ask=False)
    # Closed: no box to write.
    adr.set("da_decision", "Accolta")
    editor.edit(p, adr)
    assert editor.widgets[DISCUSSION].closed and not hasattr(editor.widgets[DISCUSSION], "text")


def test_the_tree_counts_the_new_messages_of_each_adr_and_cq(app, tmp_path):
    from arcadia_tool.ui.main_window import MainWindow

    p, da, t2, adr, cq = project(tmp_path)
    d.post(p, cq, user(MARIO, "Mario Rossi"), "Prima")
    d.post(p, cq, user(MARIO, "Mario Rossi"), "Seconda")
    p.save()
    from arcadia_tool.accounts import Account
    window = MainWindow()
    window.user = Account(id=ANNA, first_name="Anna", last_name="Bianchi", username="anna", email="a@b.it")
    window._set_project(p)
    window.tree.reload()
    item = window.tree._items[cq.uuid]
    from arcadia_tool.ui.model_tree import UNREAD_ROLE
    assert item.text(1) == "2 nuovi" and item.data(0, UNREAD_ROLE)  # the blue dot
    adr_item = window.tree._items[adr.uuid]  # Anna is of the DA: told the ADR of another team
    assert adr_item.text(1) == "" and adr_item.data(0, UNREAD_ROLE)
    window._open_finding(cq.uuid)  # read in its sheet
    app.processEvents()
    assert item.text(1) == "" and not item.data(0, UNREAD_ROLE)  # seen: no dot
    window.close()


def test_messages_sent_in_the_same_instant_keep_their_order(tmp_path):
    p, da, t2, adr, cq = project(tmp_path)
    mario = user(MARIO, "Mario Rossi")
    for n in range(30):  # far quicker than the clock
        d.post(p, adr, mario, f"Messaggio {n}")
    messages = d.messages_of(p.model, adr)
    assert [m.get("text") for m in messages] == [f"Messaggio {n}" for n in range(30)]
    assert len({m.get("posted") for m in messages}) == 30
