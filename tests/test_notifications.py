"""The notifications of the members of a team: the ADR of the other teams that concern a domain of theirs as a
destination (created, changed, deleted), the messages of their discussions; read, unread again, and the readings
recorded in the project."""
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication

from arcadia_tool.model import discussions as d
from arcadia_tool.model import notifications as n
from arcadia_tool.model.schema import ADR_FUNCTION, ADR_MERGE_DOMAINS, ADR_NEW_DOMAIN, ADR_SECTION
from arcadia_tool.storage.project import Project

MARIO, LUCA, ANNA = "b" * 32, "c" * 32, "a" * 32


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def user(account, name):
    return SimpleNamespace(id=account, full_name=name)


def project(tmp_path):
    p = Project.create(tmp_path / "p", "Prova")
    teams = {"T1": p.new_element("team", id="T1", name="RFI", design_authority=True,
                                 members=[{"name": "Anna Bianchi", "account": ANNA}]),
             "T2": p.new_element("team", id="T2", name="FBK", members=[{"name": "Mario Rossi", "account": MARIO}]),
             "T3": p.new_element("team", id="T3", name="UniMiB", members=[{"name": "Luca Guglielmo", "account": LUCA}])}
    domains = {"DF01": p.new_element("domain", id="DF01", name="Trackside", team=teams["T3"].uuid),
               "DF04": p.new_element("domain", id="DF04", name="Track Description", team=teams["T2"].uuid),
               "DF07": p.new_element("domain", id="DF07", name="Protection", team=teams["T1"].uuid)}
    adr = p.new_element("adr", id="ADR-044", title="Spostamento 3.10.1.3.1", adr_type=ADR_SECTION,
                        status="Proposta", proposer=teams["T3"].uuid, primary_proposed=domains["DF04"].uuid)
    p.save()
    return p, teams, domains, adr


def show(p, who):
    return [(x.event, x.title, x.unread) for x in n.collect(p, who)]


def test_the_teams_of_the_destination_domains_are_notified_not_the_proposer(tmp_path):
    p, teams, domains, adr = project(tmp_path)
    mario, luca, anna = user(MARIO, "Mario Rossi"), user(LUCA, "Luca Guglielmo"), user(ANNA, "Anna Bianchi")
    assert show(p, mario) == [(n.NEW, "ADR-044 · Spostamento 3.10.1.3.1", True)]
    assert n.collect(p, mario)[0].detail == "Riguarda DF04 (dominio principale proposto)"
    assert show(p, luca) == []  # the proposer
    # Anna is of the Design Authority: told every ADR not opened by the DA, apart from those of her team.
    as_da = n.collect(p, anna)[0]
    assert as_da.scopes == {n.DA} and as_da.detail == "Proposta da T3 · verso DF04 (T2) · Proposta"
    adr.set("contributors_proposed", [domains["DF07"].uuid])  # DF07 is of the DA team: for her team too
    p.update(adr)
    both = n.collect(p, anna)[0]
    assert both.scopes == {n.TEAM, n.DA} and both.detail == "Riguarda DF07 (contributore proposto)"
    # The other types: the domain proposed for a function, the team proposed for a new domain or a merge.
    sf = p.new_element("system_function", name="Validare i messaggi", domain=domains["DF01"].uuid)
    move = p.new_element("adr", id="ADR-050", adr_type=ADR_FUNCTION, status="Proposta", proposer=teams["T3"].uuid,
                         function=sf.uuid, to_domain=domains["DF04"].uuid)
    assert set(n.destination_teams(p.model, move)) == {teams["T2"].uuid}
    new = p.new_element("adr", id="ADR-051", adr_type=ADR_NEW_DOMAIN, status="Proposta", proposer=teams["T2"].uuid,
                        team_proposed=teams["T3"].uuid)
    assert [r for _e, r in n.roles_for(p.model, new, luca)] == ["team proposto"]
    merge = p.new_element("adr", id="ADR-052", adr_type=ADR_MERGE_DOMAINS, status="Proposta",
                          proposer=teams["T1"].uuid, merged_domains=[domains["DF01"].uuid, domains["DF04"].uuid])
    assert set(n.destination_teams(p.model, merge)) == {teams["T2"].uuid, teams["T3"].uuid}
    # Received already decided: nothing to look at.
    p.new_element("adr", id="ADR-053", adr_type=ADR_SECTION, status="Decisa", proposer=teams["T3"].uuid,
                  primary_proposed=domains["DF04"].uuid)
    assert "ADR-053" not in " ".join(t for _e, t, _u in show(p, mario))


def test_read_unread_again_changed_moved_and_deleted(tmp_path):
    p, teams, domains, adr = project(tmp_path)
    mario = user(MARIO, "Mario Rossi")
    p.save()
    n.mark_read(p, mario, n.collect(p, mario)[0])
    assert not p.model.of_kind("reading") and not p.is_modified  # on this PC only: the model does not change
    assert show(p, mario) == [(n.NEW, "ADR-044 · Spostamento 3.10.1.3.1", False)] and n.unread_count(p, mario) == 0
    n.mark_unread(p, mario, n.collect(p, mario)[0])  # to look at it again: on this PC only
    assert n.unread_count(p, mario) == 1
    n.mark_read(p, mario, n.collect(p, mario)[0])
    # Changed in any field: notified as changed, with the fields.
    adr.set("realloc_reason", "Perché i dati sono memorizzati a bordo")
    adr.set("status", "In revisione DA")
    changed = n.collect(p, mario)[0]
    assert changed.event == n.CHANGED and changed.unread
    assert changed.detail == "Campi modificati: Motivazione della riallocazione, Stato"
    n.mark_read(p, mario, changed)
    assert not n.collect(p, mario)[0].unread
    # Moved to a domain of another team: the notification follows it.
    adr.set("primary_proposed", domains["DF07"].uuid)
    p.update(adr)
    moved = n.collect(p, mario)[0]
    assert moved.unread and "non riguarda più i domini del tuo team" in moved.detail
    assert [x.title for x in n.collect(p, user(ANNA, "Anna Bianchi"))] == ["ADR-044 · Spostamento 3.10.1.3.1"]
    adr.set("primary_proposed", domains["DF04"].uuid)
    n.mark_read(p, mario, n.collect(p, mario)[0])
    # Deleted: notified as deleted, then read.
    p.delete_element(adr.uuid)
    deleted = n.collect(p, mario)[0]
    assert (deleted.event, deleted.title, deleted.unread) == (n.DELETED, "ADR-044 · Spostamento 3.10.1.3.1", True)
    n.mark_read(p, mario, deleted)
    assert n.unread_count(p, mario) == 0


def test_the_messages_of_the_discussions_of_the_user_are_notified(tmp_path):
    p, teams, domains, adr = project(tmp_path)
    mario, luca = user(MARIO, "Mario Rossi"), user(LUCA, "Luca Guglielmo")
    message = d.post(p, adr, luca, "Ci date un parere sulla destinazione?")
    elsewhere = p.new_element("clarification", problem="Altro", status="Aperta", recipient=teams["T1"].uuid)
    d.post(p, elsewhere, luca, "Non riguarda Mario")
    notes = [x for x in n.collect(p, mario) if x.event == n.MESSAGE]
    assert [(x.detail, x.unread) for x in notes] == [
        ("Messaggio di Luca Guglielmo: Ci date un parere sulla destinazione?", True)]
    assert [x.event for x in n.collect(p, mario)] == [n.NEW, n.MESSAGE]  # the ADR first
    n.mark_read(p, mario, notes[0])
    assert d.unread_count(p, adr, mario) == 0
    n.mark_unread(p, mario, [x for x in n.collect(p, mario) if x.event == n.MESSAGE][0])
    assert d.unread_count(p, adr, mario) == 1 and message.uuid not in d.seen(p, adr)
    # The proposer is told the messages of the others in the discussion of their ADR.
    d.post(p, adr, mario, "Va bene per noi")
    assert [x.detail for x in n.collect(p, luca) if x.event == n.MESSAGE] == [
        "Messaggio di Mario Rossi: Va bene per noi"]


def test_opening_an_adr_does_not_change_the_model(app, tmp_path):
    from arcadia_tool.ui.main_window import MainWindow

    p, teams, domains, adr = project(tmp_path)
    p.save()
    p.publish("v1", "Prova <prova@example.com>")
    window = MainWindow()
    window.user = user(MARIO, "Mario Rossi")
    window.user.username, window.user.email = "mario", "m@x.it"
    window._set_project(p)
    window._open_finding(adr.uuid)
    assert n.unread_count(p, window.user) == 0  # its notification is read
    assert not p.is_modified and not p.has_unpublished_changes() and not p.model.of_kind("reading")
    window._set_project(None)
    window.close()


def test_the_bell_the_panel_the_alert_the_sheet_and_the_tree(app, tmp_path, monkeypatch):
    from arcadia_tool.accounts import Account
    from arcadia_tool.ui import notifications as ui
    from arcadia_tool.ui.main_window import MainWindow

    p, teams, domains, adr = project(tmp_path)
    d.post(p, adr, user(LUCA, "Luca Guglielmo"), "Un parere?")
    p.save()
    window = MainWindow()
    window.user = Account(id=MARIO, first_name="Mario", last_name="Rossi", username="mario", email="m@r.it")
    window._set_project(p)
    window._refresh_state()
    assert window.notifications_action.text() == "Notifiche (2)"
    window.tree.reload()
    from arcadia_tool.ui.model_tree import UNREAD_ROLE
    item = window.tree._items[adr.uuid]
    assert item.text(1) == "1 nuovo" and item.data(0, UNREAD_ROLE)  # the blue dot on its left, the new message
    # No alert: the red dot on the bell and the count in the status bar, a click on it opens the panel.
    assert not hasattr(window, "alert_notifications")
    status = window.status_notifications.text()
    assert "<b>2</b> notifiche da leggere" in status and "DA" not in status and "href" in status
    assert window.status_notifications in window.statusBar().findChildren(type(window.status_notifications))
    # The panel: read, unread again, all read; open. The count of the status bar follows.
    dialog = ui.NotificationsDialog(p, window.user)
    dialog.changed.connect(window._show_notifications_count)
    assert dialog.summary.text() == "2 notifiche non lette" and dialog.tree.topLevelItemCount() == 2
    dialog.tree.topLevelItem(0).setSelected(True)
    dialog.read_button.click()
    assert dialog.summary.text() == "1 notifica non letta"
    assert "<b>1</b> notifica da leggere" in window.status_notifications.text()
    dialog.tree.topLevelItem(1).setSelected(True)  # the ADR, now read: after the unread message
    assert dialog.unread_button.isEnabled()
    dialog.unread_button.click()
    assert dialog.summary.text() == "2 notifiche non lette"
    dialog.only_unread.setChecked(True)
    dialog.all_button.click()
    assert dialog.summary.text() == "Nessuna notifica non letta" and dialog.tree.topLevelItemCount() == 0
    assert "Nessuna notifica da leggere" in window.status_notifications.text()
    assert window.notifications_action.text() == "Notifiche"
    dialog.only_unread.setChecked(False)
    n.mark_unread(p, window.user, n.collect(p, window.user)[0])
    dialog.fill()
    opened = []
    dialog.open_requested.connect(opened.append)
    dialog.open(dialog.tree.topLevelItem(0))
    assert opened == [adr.uuid] and n.unread_count(p, window.user) == 0
    # The sheet of the ADR: opening it reads its notification; who read it is not shown.
    n.mark_unread(p, window.user, n.collect(p, window.user)[0])
    window._open_finding(adr.uuid)
    app.processEvents()
    assert n.unread_count(p, window.user) == 0 and window.notifications_action.text() == "Notifiche"
    editor = window.editors[adr.uuid]
    texts = [w.text() for w in editor.widget().findChildren(type(dialog.summary))]
    assert not any("Mario Rossi" in t or t.startswith("Vista da") for t in texts)
    assert window.tree._items[adr.uuid].text(1) == "" and not window.tree._items[adr.uuid].data(0, UNREAD_ROLE)
    window.close()


def test_the_design_authority_is_told_every_adr_not_opened_by_it(app, tmp_path):
    from arcadia_tool.ui import notifications as ui

    p, teams, domains, adr = project(tmp_path)
    anna, mario = user(ANNA, "Anna Bianchi"), user(MARIO, "Mario Rossi")
    other = p.new_element("adr", id="ADR-045", title="Senza destinazione", adr_type=ADR_SECTION, status="Proposta",
                          proposer=teams["T2"].uuid)
    by_da = p.new_element("adr", id="ADR-046", title="Della DA", adr_type=ADR_SECTION, status="Proposta",
                          proposer=teams["T1"].uuid, primary_proposed=domains["DF04"].uuid)
    member = p.new_element("adr", id="ADR-047", title="Di un membro della DA", adr_type=ADR_SECTION,
                           status="Proposta", proposer=teams["T2"].uuid, proposer_member="Anna Bianchi")
    titles = {x.title.split(" · ")[0] for x in n.collect(p, anna)}
    assert titles == {"ADR-044", "ADR-045"}  # not those opened by the DA (its team, or one of its members)
    assert "ADR-046" in {x.title.split(" · ")[0] for x in n.collect(p, mario)}  # the destination team, yes
    assert n.unread_by_scope(p, anna) == {n.PERSONAL: 0, n.TEAM: 0, n.DA: 2, n.REFERENT: 0, n.MESSAGES: 0}
    n.mark_read(p, anna, next(x for x in n.collect(p, anna) if x.subject == other.uuid))
    assert member.uuid and by_da.uuid
    # The panel: a tab for the DA (only for its members), with its count.
    dialog = ui.NotificationsDialog(p, anna)
    labels = [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())]
    assert labels == ["Tutte (1)", "Per me", "Il mio team", "Design Authority (1)", "Messaggi"]
    dialog.tabs.setCurrentIndex(2)  # «Il mio team»
    assert dialog.tree.topLevelItemCount() == 0
    dialog.tabs.setCurrentIndex(3)
    assert dialog.tree.topLevelItemCount() == 2  # ADR-044 unread, ADR-045 read
    of_mario = ui.NotificationsDialog(p, mario).tabs  # not of the DA: no tab for it
    assert [of_mario.tabText(i) for i in range(of_mario.count())] == ["Tutte (2)", "Per me (1)", "Il mio team (2)",
                                                                     "Messaggi"]
    # The status bar of a member of the DA: those for the DA too.
    from arcadia_tool.accounts import Account
    from arcadia_tool.ui.main_window import MainWindow
    window = MainWindow()
    window.user = Account(id=ANNA, first_name="Anna", last_name="Bianchi", username="anna", email="a@b.it")
    window._set_project(p)
    window._refresh_state()
    assert "<b>1</b> notifica da leggere (di cui 1 per la DA)" in window.status_notifications.text()
    window._set_project(None)
    window.close()


def test_the_notifications_are_worked_out_once_for_a_state(tmp_path):
    p, teams, domains, adr = project(tmp_path)
    mario = user(MARIO, "Mario Rossi")
    first = n.collect(p, mario)
    calls = []
    original = n._collect
    n._collect = lambda *a: calls.append(a) or original(*a)
    try:
        for _ in range(50):  # the bell, the tree, the panel: asked often
            assert n.collect(p, mario) == first
        assert not calls
        adr.set("realloc_reason", "Cambiata")
        p.update(adr)  # the project changed: worked out again
        assert n.collect(p, mario)[0].event == n.NEW and len(calls) == 1
        n.mark_read(p, mario, n.collect(p, mario)[0])  # what the user has seen changed: again
        assert not n.collect(p, mario)[0].unread
    finally:
        n._collect = original


def test_the_state_is_new_until_the_user_of_this_pc_opens_it(app, tmp_path):
    from arcadia_tool.ui import notifications as ui

    p, teams, domains, adr = project(tmp_path)
    mario, anna = user(MARIO, "Mario Rossi"), user(ANNA, "Anna Bianchi")
    giulia = user("d" * 32, "Giulia Verdi")  # a colleague of Mario, of the same team
    members = list(teams["T2"].get("members")) + [{"name": "Giulia Verdi", "account": "d" * 32}]
    teams["T2"].set("members", members)
    p.update(teams["T2"])
    message = d.post(p, adr, user(LUCA, "Luca Guglielmo"), "Un parere?")
    n.mark_read(p, giulia, next(x for x in n.collect(p, giulia) if x.message is None))  # read by Giulia
    first = {x.key: x for x in n.collect(p, mario)}
    assert first[f"adr:{adr.uuid}"].state == n.NEW and first[f"msg:{message.uuid}"].state == n.NEW
    for x in first.values():
        n.mark_read(p, mario, x)
    assert {x.state for x in n.collect(p, mario)} == {n.READ}
    adr.set("realloc_reason", "Cambiata dopo")
    p.update(adr)
    changed = next(x for x in n.collect(p, mario) if x.message is None)
    assert changed.unread and changed.state == n.READ  # opened before: still «Letta», to look at again
    for x in n.collect(p, mario):
        n.mark_unread(p, mario, x)  # to look at it again: back to «Nuova»
    assert {(x.state, x.unread) for x in n.collect(p, mario)} == {(n.NEW, True)}
    dialog = ui.NotificationsDialog(p, mario)
    assert dialog.tree.headerItem().text(ui.STATE) == "Stato"
    assert [dialog.tree.topLevelItem(i).text(ui.STATE) for i in range(dialog.tree.topLevelItemCount())] == \
        ["Nuova", "Nuova"]
    dialog.all_button.click()
    states = [dialog.tree.topLevelItem(i).text(ui.STATE) for i in range(dialog.tree.topLevelItemCount())]
    assert states == ["Letta", "Letta"]
    dialog.tree.topLevelItem(0).setSelected(True)
    assert dialog.unread_button.isEnabled() and not dialog.read_button.isEnabled()  # «Letta»: it can go back
    dialog.unread_button.click()
    assert dialog.tree.topLevelItem(0).text(ui.STATE) == "Nuova"
    assert dialog.tree.topLevelItem(1).text(ui.DETAIL) == "Messaggio di Luca Guglielmo: Un parere?"
    header = [dialog.tree.headerItem().text(i) for i in range(dialog.tree.columnCount())]
    assert header == ["ID", "Titolo", "Descrizione", "Tipo", "Stato", "Data e ora"]
    rows = {dialog.tree.topLevelItem(i).text(ui.KIND): dialog.tree.topLevelItem(i) for i in range(2)}
    assert set(rows) == {"ADR", "Messaggio (ADR)"}
    for row in rows.values():
        assert row.text(ui.IDENT) == adr.get("id") and row.text(ui.TITLE) == adr.get("title")


def test_the_design_authority_removes_the_readings_of_the_earlier_versions(app, tmp_path, monkeypatch):
    from arcadia_tool.ui import main_window as mw

    p, teams, domains, adr = project(tmp_path)
    reading = p.new_element("reading", adr=adr.uuid, member="Mario Rossi")  # as written up to the version 0.9.4
    other = p.new_element("team", name="Non salvato")
    file = p.element_file(reading)
    p.save(only={reading.uuid, *(e.uuid for e in p.model if e.uuid != other.uuid)})
    assert file.is_file() and other.uuid in p.pending()
    mario, anna = user(MARIO, "Mario Rossi"), user(ANNA, "Anna Bianchi")
    for account in (mario, anna):
        account.username, account.email = "u", "u@x.it"
    window = mw.MainWindow()
    window._set_project(p)
    assert file.is_file()  # opening the project removes nothing
    window.user = mario  # not of the DA: refused
    window._refresh_state()
    assert not window.remove_readings_action.isEnabled()
    window.remove_readings()
    assert p.model.get(reading.uuid) is reading
    window.user = anna
    window._refresh_state()
    assert window.remove_readings_action.isEnabled()
    window.remove_readings()  # the answer of the tests: «No»
    assert p.model.get(reading.uuid) is reading and file.is_file()
    monkeypatch.setattr(mw.QMessageBox, "question", lambda *a, **k: mw.QMessageBox.Yes)
    window.remove_readings()
    assert p.model.get(reading.uuid) is None and not file.exists()
    assert other.uuid in p.pending()  # the other changes are not saved with them
    assert not window.remove_readings_action.isEnabled()
    window._set_project(None)
    window.close()



def test_an_adr_opened_by_the_da_reaches_every_member_of_the_teams_it_impacts(tmp_path):
    from arcadia_tool.model.schema import ADR_DOMAIN_SCOPE, ADR_OTHER

    p, teams, domains, adr = project(tmp_path)
    mario, luca, anna = user(MARIO, "Mario Rossi"), user(LUCA, "Luca Guglielmo"), user(ANNA, "Anna Bianchi")
    p.delete_element(adr.uuid)
    p.save()
    # The DA (T1) redefines the scope of DF01 (of T3): Luca is told, also «Per me»; Mario (T2) is not.
    scope = p.new_element("adr", id="ADR-060", title="Perimetro DF01", adr_type=ADR_DOMAIN_SCOPE, status="Proposta",
                          proposer=teams["T1"].uuid, proposer_member="Anna Bianchi", domain=domains["DF01"].uuid)
    p.save()
    told = n.collect(p, luca)
    assert [x.ident for x in told] == ["ADR-060"] and told[0].scopes == {n.TEAM, n.PERSONAL}
    assert told[0].detail == "Riguarda DF01 (dominio interessato)"  # its domain, named in the ADR
    assert n.collect(p, mario) == [] and n.collect(p, anna) == []  # another team; the DA opened it
    # A decision of the DA about no domain: for every team.
    p.new_element("adr", id="ADR-061", title="Regola comune", adr_type=ADR_OTHER, status="Proposta",
                  proposer=teams["T1"].uuid)
    p.save()
    for who in (mario, luca):
        found = {x.ident: x for x in n.collect(p, who)}
        assert "ADR-061" in found and found["ADR-061"].scopes == {n.TEAM, n.PERSONAL}
        assert found["ADR-061"].detail == "Riguarda ADR della Design Authority per tutti i team"
    del scope
    p.close()


def test_the_decision_of_the_da_reaches_whom_it_concerns_directly(tmp_path):
    from arcadia_tool.model.schema import ADR_DOMAIN_SCOPE

    p, teams, domains, adr = project(tmp_path)
    mario, luca, anna = user(MARIO, "Mario Rossi"), user(LUCA, "Luca Guglielmo"), user(ANNA, "Anna Bianchi")
    p.delete_element(adr.uuid)
    old = p.new_element("adr", id="ADR-070", title="Già decisa", adr_type=ADR_DOMAIN_SCOPE, status="Decisa",
                        proposer=teams["T2"].uuid, proposer_member="Mario Rossi", domain=domains["DF04"].uuid,
                        da_decision="Accolta")
    mine = p.new_element("adr", id="ADR-071", title="Perimetro DF01", adr_type=ADR_DOMAIN_SCOPE, status="Proposta",
                         proposer=teams["T2"].uuid, proposer_member="Mario Rossi", domain=domains["DF01"].uuid)
    p.save()
    assert n.collect(p, mario) == []  # his own ADR; the decisions already there: taken as seen
    n.collect(p, luca)
    for x in n.collect(p, luca):
        n.mark_read(p, luca, x)
    mine.set("da_decision", "Commenti DA")  # the DA asks for changes
    mine.set("da_notes", "Precisare il perimetro")
    p.update(mine)
    told = [x for x in n.collect(p, mario) if x.event == n.DECISION]
    assert [(x.ident, x.unread) for x in told] == [("ADR-071", True)]
    assert told[0].scopes == {n.TEAM, n.PERSONAL} and told[0].detail == "Decisione della DA: Commenti DA · Proposta"
    # Luca's team (DF01) is told by the notification of the ADR itself, which says the decision first.
    changed = next(x for x in n.collect(p, luca) if x.ident == "ADR-071")
    assert changed.event == n.CHANGED and changed.detail.startswith("Decisione della DA: Commenti DA · Campi")
    assert not [x for x in n.collect(p, luca) if x.event == n.DECISION]
    assert not [x for x in n.collect(p, anna) if x.event == n.DECISION]  # the DA decided it
    n.mark_read(p, mario, told[0])
    assert not [x for x in n.collect(p, mario) if x.unread]
    mine.set("da_decision", "Accolta")  # decided: told again
    p.update(mine)
    again = [x for x in n.collect(p, mario) if x.event == n.DECISION and x.unread]
    assert [x.detail for x in again] == ["Decisione della DA: Accolta · Proposta"]
    assert old.uuid not in {x.subject for x in n.collect(p, mario) if x.unread}
    p.close()
