"""The discussion of an ADR or of a CQ: the messages the members of the teams write under it, in a row, each
answering, if it wants, an earlier one. Each message is an element of its own (kind «message», a file of its own):
two messages written at the same time on two branches are both kept when the branches are merged.

The discussion closes when the Design Authority approves the ADR (decided, or accepted) or when the CQ is closed:
its messages are then only read. A message is changed or deleted only by its author (deleted: it stays as «messaggio
eliminato», so that the answers keep their place); the Design Authority hides one if needed. The files attached
are kept in the project (assets/discussions/<message>/<name>), as the figures of the SRS items."""
import re
from datetime import datetime, timedelta

from arcadia_tool.model.adr import APPROVED, outcome
from arcadia_tool.model.element import Element
from arcadia_tool.model.teams import is_da_member, memberships, normalize_account_id

KIND = "message"
SUBJECTS = ("adr", "clarification")
ASSETS = "assets/discussions"
MAX_ATTACHMENT = 20 * 1024 * 1024  # bytes: larger files would weigh on every copy of the repository


def now():
    return datetime.now().isoformat(timespec="milliseconds")


def _after(model, subject):
    """The time of a new message: now, and after the last message of the discussion (two messages sent within the
    same instant keep the order they were written in)."""
    time = now()
    last = max((m.get("posted") or "" for m in messages_of(model, subject)), default="")
    if time <= last:
        try:
            time = (datetime.fromisoformat(last) + timedelta(milliseconds=1)).isoformat(timespec="milliseconds")
        except ValueError:
            pass
    return time


def when(text):
    """«04/11/2026 10:15» from the time of a message."""
    try:
        return f"{datetime.fromisoformat(text):%d/%m/%Y %H:%M}"
    except (TypeError, ValueError):
        return text or ""


def messages_of(model, subject):
    """The messages of the discussion of an ADR or a CQ (an element or its uuid), the oldest first."""
    uuid = getattr(subject, "uuid", subject)
    return sorted((m for m in model.of_kind(KIND) if m.get("subject") == uuid),
                  key=lambda m: (m.get("posted") or "", m.uuid))


def closed(model, subject):
    """Why the discussion is closed (only read), or None: an ADR approved by the Design Authority, a CQ closed."""
    if subject.kind == "adr" and outcome(subject) == APPROVED:
        return "L'ADR è stata approvata dalla Design Authority: la discussione è chiusa."
    if subject.kind == "clarification" and subject.get("status") == "Chiusa":
        return "La richiesta di chiarimento è chiusa: la discussione è chiusa."
    return None


def is_author(message, user):
    account = normalize_account_id(getattr(user, "id", "")) if user is not None else ""
    return bool(account) and normalize_account_id(message.get("author_account")) == account


def write_denied(model, subject, user):
    """Why the user may not write in the discussion, or None: only the members of the teams, while it is open."""
    reason = closed(model, subject)
    if reason:
        return reason
    if user is None or not memberships(model, user):
        return "Scrivono nelle discussioni i membri dei team del progetto."
    return None


def may_change(model, message, user):
    """The author changes or deletes their message (the discussion open)."""
    subject = model.get(message.get("subject"))
    return is_author(message, user) and not message.get("deleted") and (subject is None or not closed(model, subject))


def may_hide(model, user):
    return user is not None and is_da_member(model, user)


def unread(model, subject, user, seen):
    """The messages of the others the user has not seen yet (seen: the uuids of those already shown to them). Not
    by time: a message written before the last reading may arrive after it (received from another branch)."""
    seen = set(seen or ())
    return [m for m in messages_of(model, subject) if not is_author(m, user) and not m.get("deleted")
            and m.uuid not in seen]


def seen(project, subject):
    """The messages of the discussion already shown on this PC (kept on this PC only, not in the project)."""
    return set((project.local_settings().get("read") or {}).get(getattr(subject, "uuid", subject)) or [])


def mark_read(project, subject):
    """All the messages of the discussion shown: none of them is new any more."""
    uuid = getattr(subject, "uuid", subject)
    read = dict(project.local_settings().get("read") or {})
    shown = sorted(m.uuid for m in messages_of(project.model, uuid))
    if read.get(uuid) != shown:
        read[uuid] = shown
        project.set_local_settings(read=read)


def unread_count(project, subject, user):
    return len(unread(project.model, subject, user, seen(project, subject)))


def attachment_path(message_uuid, name):
    """Where a file attached is kept: its name made safe for any file system."""
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .") or "allegato"
    return f"{ASSETS}/{message_uuid}/{safe}"


def attachment_name(path):
    return path.rsplit("/", 1)[-1]


def post(project, subject, user, text, team=None, reply_to=None, files=()):
    """A new message of the user in the discussion of the subject, with the files [(name, bytes)]. team: the team
    the user writes for (by default the first one they belong to). Returns the message (to be saved)."""
    teams = [t for t, _row in memberships(project.model, user)] if user is not None else []
    team = team or (teams[0] if teams else None)
    message = Element(KIND)
    names = []
    for name, data in files:
        path = attachment_path(message.uuid, name)
        while path in names:  # two files with the same name
            stem, dot, ext = path.rpartition(".")
            path = f"{stem}_2.{ext}" if dot else f"{path}_2"
        names.append(path)
        project.set_asset(path, data)
    values = {"subject": subject.uuid, "author": getattr(user, "full_name", "") or "",
              "author_account": normalize_account_id(getattr(user, "id", "")), "team": team.uuid if team else None,
              "posted": _after(project.model, subject), "text": text.strip(),
              "reply_to": reply_to.uuid if reply_to else None,
              "attachments": names}
    for name, value in values.items():
        if value not in (None, "", []):
            message.set(name, value)
    project.update(message)
    return message


def edit(project, message, text):
    previous = message.copy()
    message.set("text", text.strip())
    message.set("edited", now())
    project.update(message, previous)


def delete(project, message):
    """Deleted by the author: the text and the files removed, the message stays as «messaggio eliminato»."""
    previous = message.copy()
    message.set("deleted", True)
    message.set("text", "")
    message.set("attachments", [])
    message.set("edited", now())
    project.update(message, previous)


def set_hidden(project, message, hidden):
    previous = message.copy()
    message.set("hidden_by_da", bool(hidden))
    project.update(message, previous)
