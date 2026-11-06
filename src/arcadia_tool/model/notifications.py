"""The notifications of a member of a team: the ADR proposed by another team that concern a domain of their team as
a destination (created, changed in any field, deleted); for the members of the Design Authority, every ADR not opened
by the DA itself (they decide on all of them); and the messages of the discussions that concern them.

Nothing is written in the project to notify: a notification is worked out from the model, compared with what the
user has already seen on this PC (the version of each ADR seen, kept in .arcadia/local.json, per account). It
arrives with the ADR itself (Pubblica, Invia, Ricevi), and follows it: a destination moved to another team moves the
notification too. Each notification says why it reaches the user (SCOPES): for their team, as Design Authority, a
message; the panel shows them apart.

A notification is read when the ADR is opened, or marked read; it can be marked unread again, to look at it again.
Reading an ADR is also recorded in the project (kind «reading»: a file per member and ADR, so that two readings on
two branches do not conflict); it is not shown to the others.

The notifications are worked out once for a state of the project and of what the user has seen (see collect): the
bell, the tree and the panel ask them often."""
import hashlib
import json
from dataclasses import dataclass, field

from arcadia_tool.model import discussions
from arcadia_tool.model.adr import OPEN
from arcadia_tool.model.element import Element
from arcadia_tool.model.schema import (ADR_DELETE_DOMAIN, ADR_DOMAIN_SCOPE, ADR_EXCLUSION, ADR_FUNCTION,
                                       ADR_IMPLEMENTATION, ADR_MERGE_DOMAINS, ADR_NEW_DOMAIN, ADR_OWNER,
                                       ADR_PRODUCT_OPTION, ADR_SECTION, ADR_SPLIT_DOMAIN, KINDS_BY_NAME)
from arcadia_tool.model.teams import design_authority, member_rows, memberships, normalize_account_id, person_key

READING = "reading"
NEW, CHANGED, DELETED, MESSAGE = "Nuova", "Modificata", "Eliminata", "Messaggio"
READ = "Letta"  # the state of a notification opened at least once (see Notification.state)
TEAM, DA, MESSAGES = "team", "da", "messages"  # why a notification reaches the user
SCOPE_LABELS = {TEAM: "Il mio team", DA: "Design Authority", MESSAGES: "Messaggi"}
# The fields of each type naming the domains (or the teams) that receive what the ADR proposes: (field, role).
DESTINATIONS = {
    ADR_SECTION: (("primary_proposed", "dominio principale proposto"),
                  ("contributors_proposed", "contributore proposto")),
    ADR_FUNCTION: (("to_domain", "dominio proposto"),),
    ADR_EXCLUSION: (("traced_by", "dominio che traccia al posto dell'escluso"),),
    ADR_MERGE_DOMAINS: (("merged_domains", "dominio da fondere"), ("kept_domain", "dominio che resta"),
                        ("team_proposed", "team proposto")),
    ADR_SPLIT_DOMAIN: (("split_domain", "dominio da scindere"), ("new_domains", "team proposto per un dominio "
                                                                               "risultante")),
    ADR_NEW_DOMAIN: (("team_proposed", "team proposto"),),
    ADR_DOMAIN_SCOPE: (("domain", "dominio interessato"),),
    ADR_DELETE_DOMAIN: (("deleted_domain", "dominio da eliminare"),),
    ADR_OWNER: (("candidate_producers", "dominio di un produttore candidato"),
                ("chosen_producer", "dominio del produttore scelto")),
    ADR_PRODUCT_OPTION: (("function", "dominio della funzione"),),
    ADR_IMPLEMENTATION: (("impl_item", "dominio principale della voce"),),
}
CONCERNS = ("concerns", "dominio interessato")  # every type: the domain the ADR was created from


@dataclass
class Notification:
    key: str  # «adr:<uuid>», «msg:<uuid>»
    event: str  # NEW, CHANGED, DELETED, MESSAGE
    subject: str  # the uuid of the ADR (or of the ADR or CQ of the message)
    title: str  # «ADR-022 · Spostamento…»
    detail: str  # the roles of the domains of the team, the fields changed, the start of the message
    when: str = ""
    unread: bool = True
    message: str = None  # the uuid of the message
    scopes: frozenset = field(default_factory=frozenset)  # TEAM, DA, MESSAGES: why it reaches the user
    # Opened (or marked read) by the user of this PC: «Letta»; else «Nuova» (never opened, or marked unread to look at
    # it again). The readings of the others, even of the same team, do not count. Changed after it was read: still
    # «Letta», but unread (to look at again).
    opened: bool = False

    @property
    def state(self):
        return READ if self.opened else NEW


def _team_of(model, element):
    """The team of a domain, of the domain of a function or of an SRS item (its principal domain)."""
    if element is None:
        return None
    if element.kind == "team":
        return element
    if element.kind == "domain":
        return model.get(element.get("team")) if element.get("team") else None
    if element.kind in ("system_function", "logical_function"):
        from arcadia_tool.model.links import _domain_of_function
        return _team_of(model, model.get(_domain_of_function(model, element)))
    if element.kind == "requirement":
        from arcadia_tool.model.adr import principal_of
        principal = principal_of(model, element)  # the uuid of the domain, or None
        return _team_of(model, model.get(principal) if isinstance(principal, str) else principal)
    return None


def destination_teams(model, adr):
    """{team uuid: [(the domain or element it is reached through, role)]}: the teams receiving what the ADR
    proposes."""
    result = {}
    for name, role in (*DESTINATIONS.get(adr.get("adr_type"), ()), CONCERNS):
        value = adr.values.get(name)
        refs = []
        if isinstance(value, str):
            refs = [value]
        elif isinstance(value, list):
            for v in value:  # a list of uuids, or the rows of a table (their team, their function)
                refs += [v] if isinstance(v, str) else [v.get("team"), v.get("function")]
        for uuid in refs:
            element = model.get(uuid) if uuid else None
            team = _team_of(model, element)
            if team is not None and (element, role) not in result.get(team.uuid, []):
                result.setdefault(team.uuid, []).append((element, role))
    return result


def my_teams(model, user):
    return {t.uuid for t, _row in memberships(model, user)} if user is not None else set()


class _Who:
    """The user in the project, worked out once: their teams, whether they are of the Design Authority, who the DA
    is (to know the ADR it opened itself)."""

    def __init__(self, model, user):
        self.model, self.user = model, user
        self.teams = my_teams(model, user)
        da = design_authority(model)
        self.da = da.uuid if da is not None else None
        self.is_da = self.da in self.teams
        self.da_people = {person_key(r.get("name")) for r in member_rows(da)} if da is not None else set()

    def opened_by_da(self, adr):
        return bool(self.da) and (adr.get("proposer") == self.da or
                                  person_key(adr.get("proposer_member") or "") in self.da_people)

    def roles(self, adr):
        """How the ADR concerns the teams of the user as a destination ([(element, role)]); [] if one of their
        teams proposed it."""
        if not self.teams or adr.get("proposer") in self.teams:
            return []
        return [r for team, roles in destination_teams(self.model, adr).items() if team in self.teams for r in roles]

    def as_da(self, adr):
        """A member of the DA is told every ADR, unless the DA opened it."""
        return self.is_da and not self.opened_by_da(adr)


def roles_for(model, adr, user):
    """How the ADR concerns the teams of the user as a destination ([(element, role)]), [] if it does not, or if
    one of their teams proposed it."""
    return _Who(model, user).roles(adr)


def fingerprint(adr):
    """A version of the ADR: what it says now (its fields), to recognize a change."""
    text = json.dumps(adr.values, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def _snapshot(adr, relevant):
    return {"hash": fingerprint(adr), "values": json.loads(json.dumps(adr.values, default=str)),
            "title": _title(adr), "relevant": relevant, "seen_at": discussions.now()}


def _title(adr):
    return " · ".join(t for t in (adr.get("id"), adr.get("title")) if t) or "ADR senza titolo"


def _changed_fields(adr, before):
    """The labels of the fields changed since the version seen."""
    schema = KINDS_BY_NAME["adr"]
    names = set(adr.values) | set(before)
    changed = [n for n in names if adr.values.get(n) != before.get(n) and n not in ("decision_date",)]
    labels = [schema.field(n).label for n in changed if schema.field(n) is not None and not schema.field(n).hidden]
    return sorted(labels)


# --- what the user has seen, on this PC ----------------------------------------------------------------------------

def _account(user):
    return normalize_account_id(getattr(user, "id", "")) or "-"


def _state(project, user, local=None):
    data = ((local or project.local_settings()).get("notifications") or {}).get(_account(user)) or {}
    return {"adr": dict(data.get("adr") or {}), "unread": list(data.get("unread") or []),
            "noticed": dict(data.get("noticed") or {}), "opened": list(data.get("opened") or [])}


def _save_state(project, user, state):
    data = dict(project.local_settings().get("notifications") or {})
    data[_account(user)] = state
    project.set_local_settings(notifications=data)


def _role_text(model, roles):
    return "; ".join(f"{(e.get('id') or model.label(e)) if e is not None else ''} ({role})".strip()
                     for e, role in roles)


def _da_text(model, adr):
    """For the Design Authority: who proposed the ADR and where it goes."""
    team = model.get(adr.get("proposer")) if adr.get("proposer") else None
    who = " · ".join(t for t in ((team.get("id") or team.get("name")) if team else "", adr.get("proposer_member"))
                     if t) or "team non indicato"
    targets = []
    for t, roles in destination_teams(model, adr).items():
        target = model.get(t)
        domains = ", ".join(sorted({e.get("id") or model.label(e) for e, _r in roles if e is not None
                                    and e.kind != "team"}))
        targets.append(f"{domains} ({target.get('id') or target.get('name')})" if domains else
                       (target.get("id") or target.get("name")))
    return f"Proposta da {who}" + (f" · verso {', '.join(targets)}" if targets else "") + \
        f" · {adr.get('status') or 'senza stato'}"


def _cache_key(project, user, local):
    return (_account(user), project.change_mark(), len(project.model.elements),
            json.dumps([local.get("notifications"), local.get("read")], sort_keys=True, default=str))


def collect(project, user):
    """The notifications of the user, the unread first (the ADR before the messages), then the newest. Worked out
    once for a state of the project and of what the user has seen on this PC."""
    if user is None:
        return []
    cached = getattr(project, "_notifications", None)
    local = project.local_settings()
    if cached is not None and cached[0] == _cache_key(project, user, local):
        return list(cached[1])
    result = _collect(project, user, local)
    project._notifications = (_cache_key(project, user, project.local_settings()), result)
    return list(result)


def _collect(project, user, local):
    model = project.model
    who = _Who(model, user)
    if not who.teams:
        return []
    state = _state(project, user, local)
    seen, forced, noticed = state["adr"], set(state["unread"]), state["noticed"]
    first_noticed = dict(noticed)

    def noticed_at(version):
        """When this PC first saw the version of the ADR (an ADR has no date of its own)."""
        return noticed.setdefault(version, discussions.now())

    result, present = [], set()
    for adr in model.of_kind("adr"):
        present.add(adr.uuid)
        roles = who.roles(adr)
        da = who.as_da(adr)
        scopes = frozenset(s for s, on in ((TEAM, roles), (DA, da)) if on)
        snap = seen.get(adr.uuid)
        if not scopes and not (snap and snap.get("relevant")):
            continue
        key = f"adr:{adr.uuid}"
        version = fingerprint(adr)
        changed = snap is not None and snap.get("hash") != version
        when = snap.get("seen_at", "") if snap is not None and not changed else noticed_at(f"{key}:{version}")
        about = "Riguarda " + _role_text(model, roles) if roles else _da_text(model, adr) if da else ""
        if snap is None:
            if adr.get("status") not in OPEN:
                continue  # received already decided: nothing to look at
            result.append(Notification(key, NEW, adr.uuid, _title(adr), about, when, True, scopes=scopes))
            continue
        if changed:
            fields = _changed_fields(adr, snap.get("values") or {})
            detail = ("Campi modificati: " + ", ".join(fields)) if fields else "Modificata"
            if not scopes:
                detail += " · non riguarda più i domini del tuo team"
        else:
            detail = about or "Non riguarda più i domini del tuo team"
        result.append(Notification(key, CHANGED if changed or not scopes else NEW, adr.uuid, _title(adr), detail,
                                   when, changed or key in forced,  # marked unread: «Nuova» again (see opened)
                                   scopes=scopes or frozenset({TEAM}),
                                   opened="hash" in snap and key not in forced))
    for uuid, snap in seen.items():  # ADR seen, and no longer in the project
        if uuid not in present and snap.get("relevant", True):
            key = f"adr:{uuid}"
            result.append(Notification(key, DELETED, uuid, snap.get("title") or "ADR", "L'ADR è stata eliminata",
                                       noticed_at(f"{key}:deleted"), not snap.get("deleted_seen") or key in forced,
                                       scopes=frozenset(snap.get("scopes") or (TEAM,)),
                                       opened="hash" in snap and key not in forced))
    if noticed != first_noticed:
        _save_state(project, user, {**state, "noticed": noticed})
    result += _messages(project, who, local, set(state["opened"]))
    result.sort(key=lambda n: n.when or "", reverse=True)
    return sorted(result, key=lambda n: (not n.unread, n.event == MESSAGE))


def _messages(project, who, local, opened=frozenset()):
    """The messages of the others in the discussions that concern the user: ADR of their teams (proposed, or as a
    destination), every ADR for the DA, CQ to their teams, and those where they wrote."""
    model, user = project.model, who.user
    by_subject = {}
    for m in model.elements.values():
        if m.kind == discussions.KIND:
            by_subject.setdefault(m.get("subject"), []).append(m)
    if not by_subject:
        return []
    read = local.get("read") or {}
    wrote = {s for s, ms in by_subject.items() if any(discussions.is_author(m, user) for m in ms)}
    result = []
    for uuid, messages in by_subject.items():
        subject = model.get(uuid)
        if subject is None:
            continue
        if subject.kind == "adr":
            concerned = subject.get("proposer") in who.teams or who.roles(subject) or who.as_da(subject)
        else:
            concerned = subject.get("recipient") in who.teams
        if not concerned and uuid not in wrote:
            continue
        seen = set(read.get(uuid) or [])
        title = _title(subject) if subject.kind == "adr" else " · ".join(
            t for t in (subject.get("id"), "richiesta di chiarimento") if t)
        for m in messages:
            if discussions.is_author(m, user) or m.get("deleted"):
                continue
            text = " ".join((m.get("text") or "").split())
            start = text if len(text) <= 120 else text[:120] + "…"
            result.append(Notification(f"msg:{m.uuid}", MESSAGE, uuid, title,
                                       f"Messaggio di {m.get('author') or 'un membro'}: {start}",
                                       m.get("posted") or "", m.uuid not in seen, m.uuid,
                                       scopes=frozenset({MESSAGES}), opened=m.uuid in seen))
    return result


def unread_count(project, user):
    return sum(1 for n in collect(project, user) if n.unread)


def unread_by_scope(project, user):
    """{TEAM: n, DA: n, MESSAGES: n}: the unread notifications for each reason."""
    counts = {TEAM: 0, DA: 0, MESSAGES: 0}
    for n in collect(project, user):
        if n.unread:
            for scope in n.scopes:
                counts[scope] += 1
    return counts


def mark_read(project, user, notification):
    """Read: the version of the ADR now is the one seen (and the reading recorded in the project); the message
    seen."""
    if notification.event == MESSAGE:
        read = dict(project.local_settings().get("read") or {})
        shown = set(read.get(notification.subject) or [])
        shown.add(notification.message)
        read[notification.subject] = sorted(shown)
        project.set_local_settings(read=read)
        return None
    state = _state(project, user)
    state["unread"] = [k for k in state["unread"] if k != notification.key]
    adr = project.model.get(notification.subject)
    if adr is None:  # deleted: seen
        state["adr"].setdefault(notification.subject, {})["deleted_seen"] = True
        _save_state(project, user, state)
        return None
    who = _Who(project.model, user)
    snap = _snapshot(adr, bool(who.roles(adr) or who.as_da(adr)))
    snap["scopes"] = sorted(notification.scopes)
    state["adr"][adr.uuid] = snap
    _save_state(project, user, state)
    return record_reading(project, user, adr)


def mark_unread(project, user, notification):
    """Unread again, «Nuova», to look at it again (on this PC only: the reading recorded in the project stays)."""
    if notification.event == MESSAGE:
        read = dict(project.local_settings().get("read") or {})
        shown = set(read.get(notification.subject) or [])
        read[notification.subject] = sorted(shown - {notification.message})
        project.set_local_settings(read=read)
        return
    state = _state(project, user)
    if notification.key not in state["unread"]:
        state["unread"].append(notification.key)
    _save_state(project, user, state)


def adr_opened(project, user, adr):
    """The ADR shown in its sheet: its notification (if any) is read. True if one was."""
    for n in collect(project, user):
        if n.subject == adr.uuid and n.event != MESSAGE and n.unread:
            mark_read(project, user, n)
            return True
    return False


# --- the readings recorded in the project --------------------------------------------------------------------------

def readings_of(model, adr):
    return sorted((r for r in model.elements.values() if r.kind == READING and r.get("adr") == adr.uuid),
                  key=lambda r: r.get("read_at") or "")


def record_reading(project, user, adr):
    """A member of a destination team, or of the Design Authority, has read the ADR: recorded in the project (one
    record per member and ADR, with the version read), saved at once. None if the user is neither."""
    model = project.model
    who = _Who(model, user)
    teams = [t for t in destination_teams(model, adr) if t in who.teams] if who.roles(adr) else []
    if not teams and who.as_da(adr):
        teams = [who.da]
    if not teams:
        return None
    account = normalize_account_id(getattr(user, "id", ""))
    record = next((r for r in readings_of(model, adr) if r.get("account") == account), None)
    version = fingerprint(adr)
    if record is not None and record.get("version") == version:
        return record
    previous = record.copy() if record is not None else None
    record = record or Element(READING)
    record.set("adr", adr.uuid)
    record.set("team", teams[0])
    record.set("member", getattr(user, "full_name", "") or "")
    record.set("account", account)
    record.set("read_at", discussions.now())
    record.set("version", version)
    project.update(record, previous)
    project.save(only={record.uuid})
    return record
