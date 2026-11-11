"""The referent of a functional domain (a member of its team, chosen in its sheet): notified of the ADR that impact
the domain and of the messages about it (its ADR, the requests for clarification on its clauses)."""
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication

from arcadia_tool.model import discussions as d
from arcadia_tool.model import notifications as n
from arcadia_tool.model.schema import ADR_DOMAIN_SCOPE, ADR_SECTION
from arcadia_tool.model.teams import referent_domains
from arcadia_tool.storage.project import Project

MARIO, LUCA, ANNA, SARA = "b" * 32, "c" * 32, "a" * 32, "d" * 32


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def user(account, name):
    return SimpleNamespace(id=account, full_name=name)


def project(tmp_path):
    p = Project.create(tmp_path / "p", "Prova")
    t1 = p.new_element("team", id="T1", name="RFI", design_authority=True,
                       members=[{"name": "Anna Bianchi", "account": ANNA}])
    t2 = p.new_element("team", id="T2", name="FBK", members=[{"name": "Mario Rossi", "account": MARIO},
                                                            {"name": "Sara Neri", "account": SARA}])
    t3 = p.new_element("team", id="T3", name="UniMiB", members=[{"name": "Luca Guglielmo", "account": LUCA}])
    df1 = p.new_element("domain", id="DF01", name="Trackside", mission="Lato terra", team=t3.uuid)
    df4 = p.new_element("domain", id="DF04", name="Track Description", team=t2.uuid,
                        referent="Sara Neri")  # a member of its team, chosen in its sheet
    section = p.new_element("requirement", id="3.10.1", item_type="Sezione", primary_domain=df4.uuid)
    p.new_element("requirement", id="3.4.1", item_type="Sezione", primary_domain=df1.uuid)  # a domain has sections
    clause = p.new_element("requirement", id="3.10.1.3", item_type="Requisito", parent=section.uuid)
    p.save()
    return p, dict(t1=t1, t2=t2, t3=t3, df1=df1, df4=df4, section=section, clause=clause)


def test_who_the_referent_is(tmp_path):
    p, e = project(tmp_path)
    assert referent_domains(p.model, user(SARA, "Sara Neri")) == {e["df4"].uuid}  # by the ID of her account
    assert referent_domains(p.model, user("f" * 32, "Sara Neri")) == set()  # another account with her name
    assert referent_domains(p.model, user(MARIO, "Mario Rossi")) == set()
    df1 = p.model.get(e["df1"].uuid)
    assert df1.get("referent") is None  # its team has no referent
    p.close()


def test_the_referent_is_notified_of_the_adr_that_impact_the_domain(tmp_path):
    p, e = project(tmp_path)
    sara, mario = user(SARA, "Sara Neri"), user(MARIO, "Mario Rossi")
    # Proposed by T3 to move a clause of DF04 to DF01: it impacts DF04 (where the clause is now).
    move = p.new_element("adr", id="ADR-044", title="Spostamento 3.10.1.3", adr_type=ADR_SECTION, status="Proposta",
                         proposer=e["t3"].uuid, realloc_item=[e["clause"].uuid], primary_proposed=e["df1"].uuid)
    # Proposed by her own team: only as referent (her team proposed it), not «Il mio team».
    scope = p.new_element("adr", id="ADR-045", title="Perimetro DF04", adr_type=ADR_DOMAIN_SCOPE, status="Proposta",
                          proposer=e["t2"].uuid, proposer_member="Mario Rossi", domain=e["df4"].uuid)
    # Proposed by herself: nothing.
    p.new_element("adr", id="ADR-046", title="Mia", adr_type=ADR_DOMAIN_SCOPE, status="Proposta",
                  proposer=e["t2"].uuid, proposer_member="Sara Neri", domain=e["df4"].uuid)
    p.save()
    found = {x.ident: x for x in n.collect(p, sara)}
    assert set(found) == {"ADR-044", "ADR-045"}
    assert found["ADR-044"].scopes == {n.REFERENT, n.PERSONAL}  # DF04 is where the clause comes from, not a destination
    assert found["ADR-045"].scopes == {n.REFERENT, n.PERSONAL}
    assert found["ADR-045"].detail == "Impatta DF04 (dominio di cui sei referente)"
    assert n.unread_by_scope(p, sara)[n.REFERENT] == 2
    assert n.collect(p, mario) == []  # not a referent, and DF04 is not a destination of ADR-044
    n.mark_read(p, sara, found["ADR-045"])
    assert n.unread_by_scope(p, sara)[n.REFERENT] == 1
    # Luca, referent of DF01 (the domain proposed): as a member of T3 he proposed it, as its referent he is told.
    df1 = p.model.get(e["df1"].uuid)
    df1.set("referent", "Luca Guglielmo")
    p.update(df1)
    assert {x.ident for x in n.collect(p, user(LUCA, "Luca Guglielmo"))} == {"ADR-044"}
    del scope
    p.close()


def test_the_referent_is_told_the_messages_about_the_clauses_of_the_domain(tmp_path):
    p, e = project(tmp_path)
    sara, luca = user(SARA, "Sara Neri"), user(LUCA, "Luca Guglielmo")
    cq = p.new_element("clarification", problem="Cosa intende?", status="Aperta", recipient=e["t3"].uuid,
                       clause=e["clause"].uuid)  # to another team, about a clause of DF04
    p.save()
    d.post(p, cq, luca, "Una domanda sulla 3.10.1.3")
    messages = [x for x in n.collect(p, sara) if x.event == n.MESSAGE]
    assert len(messages) == 1 and messages[0].kind == "Messaggio (CQ)"
    assert n.collect(p, user(MARIO, "Mario Rossi")) == []  # not a referent: nothing
    p.close()


def test_the_panel_has_the_tab_of_the_referent(app, tmp_path):
    from arcadia_tool.ui.notifications import NotificationsDialog

    p, e = project(tmp_path)
    p.new_element("adr", id="ADR-045", title="Perimetro DF04", adr_type=ADR_DOMAIN_SCOPE, status="Proposta",
                  proposer=e["t3"].uuid, domain=e["df4"].uuid)
    p.save()
    dialog = NotificationsDialog(p, user(SARA, "Sara Neri"))
    tabs = [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())]
    assert "Referente di dominio (1)" in tabs
    dialog = NotificationsDialog(p, user(MARIO, "Mario Rossi"))  # not a referent: no tab
    assert not any(t.startswith("Referente") for t in (dialog.tabs.tabText(i) for i in range(dialog.tabs.count())))
    p.close()


def test_for_me_collects_what_is_directed_to_the_user(app, tmp_path):
    from arcadia_tool.ui.notifications import NotificationsDialog

    p, e = project(tmp_path)
    sara, luca = user(SARA, "Sara Neri"), user(LUCA, "Luca Guglielmo")
    # On her domain (DF04): for her.
    scope = p.new_element("adr", id="ADR-045", title="Perimetro DF04", adr_type=ADR_DOMAIN_SCOPE, status="Proposta",
                          proposer=e["t3"].uuid, domain=e["df4"].uuid)
    # Proposed by her: the messages of the others in its discussion are for her.
    mine = p.new_element("adr", id="ADR-047", title="Mia", adr_type=ADR_DOMAIN_SCOPE, status="Proposta",
                         proposer=e["t2"].uuid, proposer_member="Sara Neri", domain=e["df1"].uuid)
    # Of another domain, she wrote in its discussion: the answers are for her.
    other = p.new_element("adr", id="ADR-048", title="Altro", adr_type=ADR_DOMAIN_SCOPE, status="Proposta",
                          proposer=e["t3"].uuid, domain=e["df1"].uuid)
    p.save()
    d.post(p, mine, luca, "Un commento alla tua ADR")
    d.post(p, other, sara, "Una mia domanda")
    d.post(p, other, luca, "La risposta")
    found = n.collect(p, sara)
    personal = sorted((x.ident, x.event) for x in found if n.PERSONAL in x.scopes)
    assert personal == [("ADR-045", n.NEW), ("ADR-047", n.MESSAGE), ("ADR-048", n.MESSAGE)]
    assert n.unread_by_scope(p, sara)[n.PERSONAL] == 3
    dialog = NotificationsDialog(p, sara)
    assert dialog.tabs.tabText(1) == "Per me (3)"  # right after «Tutte»
    dialog.tabs.setCurrentIndex(1)
    assert dialog.tree.topLevelItemCount() == 3
    del scope
    p.close()


def test_only_the_design_authority_chooses_the_referent(app, tmp_path):
    from arcadia_tool.model.teams import edit_denied
    from arcadia_tool.ui.element_editor import ElementEditor

    p, e = project(tmp_path)
    mario, anna = user(MARIO, "Mario Rossi"), user(ANNA, "Anna Bianchi")  # FBK (the team of DF04); the DA
    assert "sceglierne il referente" in edit_denied(p.model, mario, "domain", "referent")
    assert edit_denied(p.model, anna, "domain", "referent") is None
    editor = ElementEditor()
    editor.field_denied = lambda name: edit_denied(p.model, mario, "domain", name)
    editor.edit(p, e["df4"], editing=True)
    picker = editor.widgets["referent"]
    assert not picker.isEnabled() and "Design Authority" in picker.toolTip()
    editor.draft.set("referent", "Mario Rossi")  # changed anyway: not saved
    editor.draft.set("mission", "Descrivere il binario")
    editor.dirty = True
    editor.save_changes()
    assert e["df4"].get("referent") == "Sara Neri" and e["df4"].get("mission") == "Descrivere il binario"
    editor = ElementEditor()
    editor.field_denied = lambda name: edit_denied(p.model, anna, "domain", name)
    editor.edit(p, e["df4"], editing=True)
    assert editor.widgets["referent"].isEnabled()  # the DA chooses it
    p.close()
