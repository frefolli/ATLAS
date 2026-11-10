"""«Analizzato»: a member of a team marks that they have at least taken an SRS clause in charge. One element per person
and clause, a file of its own (as the messages of the discussions): marks made at the same time on two branches are
all kept by the merge, and taking a mark back removes only that one.

The person who marked takes it back with another click (Analizzato → Non analizzato); another person, of the same team
or of another one, adds their own mark, and the clause shows how many people have analysed it."""
from datetime import datetime

from arcadia_tool.model.element import Element
from arcadia_tool.model.teams import memberships, normalize_account_id

KIND = "analysis"


def now():
    return datetime.now().isoformat(timespec="seconds")


def marks_by_requirement(model):
    """{uuid of a clause: its marks, the oldest first}."""
    found = {}
    for m in model.of_kind(KIND):
        found.setdefault(m.get("requirement"), []).append(m)
    for marks in found.values():
        marks.sort(key=lambda m: m.get("marked_at") or "")
    return found


def marks_of(model, requirement):
    return marks_by_requirement(model).get(getattr(requirement, "uuid", requirement), [])


def is_mine(mark, user):
    """The mark is of the user: by the ID of their account, else (no ID) by their name."""
    if user is None:
        return False
    account = normalize_account_id(getattr(user, "id", ""))
    if account and normalize_account_id(mark.get("account")):
        return normalize_account_id(mark.get("account")) == account
    name = (getattr(user, "full_name", "") or "").strip().lower()
    return bool(name) and (mark.get("member") or "").strip().lower() == name


def mark_denied(model, user):
    """Why the user may not mark the clauses, or None: only the members of the teams of the project."""
    if user is None or not memberships(model, user):
        return "Segnano le voci come analizzate i membri dei team del progetto."
    return None


def toggle(project, requirement, user):
    """The mark of the user on the clause: added if they had none, removed if they had one. Returns (the uuids
    changed, to save; True if now marked by the user)."""
    mine = [m for m in marks_of(project.model, requirement) if is_mine(m, user)]
    if mine:
        for m in mine:
            project.delete_element(m.uuid)
        return [m.uuid for m in mine], False
    teams = [t for t, _row in memberships(project.model, user)]
    mark = Element(KIND)
    values = {"requirement": requirement.uuid, "member": getattr(user, "full_name", "") or "",
              "account": normalize_account_id(getattr(user, "id", "")), "team": teams[0].uuid if teams else None,
              "marked_at": now()}
    for name, value in values.items():
        if value not in (None, ""):
            mark.set(name, value)
    project.update(mark)
    return [mark.uuid], True


def when(text):
    """«10/11/2026 alle 10:15» from «2026-11-10T10:15:00»."""
    try:
        moment = datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return text or ""
    return moment.strftime("%d/%m/%Y alle %H:%M")


def who_text(model, marks):
    """Who has analysed the clause, one per line, the oldest first."""
    lines = []
    for m in marks:
        team = model.get(m.get("team"))
        team = f" ({model.label(team)})" if team is not None else ""
        lines.append(f"• {m.get('member') or 'Senza nome'}{team} · {when(m.get('marked_at'))}")
    return "\n".join(lines)
