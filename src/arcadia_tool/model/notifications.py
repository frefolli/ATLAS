"""The notifications of a member of a team: the ADR proposed by another team that concern a domain of their team as
a destination (created, changed in any field, deleted); for the members of the Design Authority, every ADR not opened
by the DA itself (they decide on all of them); for the referents of a functional domain, every ADR that impacts it
(see adr.impacted_domains) and the messages about the clauses of the domain; and the messages of the discussions
that concern them.

Nothing is written in the project to notify: a notification is worked out from the model, compared with what the
user has already seen on this PC (the version of each ADR seen, kept in .arcadia/local.json, per account). It
arrives with the ADR itself (Pubblica, Invia, Ricevi), and follows it: a destination moved to another team moves the
notification too. Each notification says why it reaches the user (SCOPES): for their team, as Design Authority, a
message; the panel shows them apart.

A notification is read when the ADR is opened, or marked read; it can be marked unread again, to look at it again:
all on this PC only, opening an ADR does not change the model.

The notifications are worked out once for a state of the project and of what the user has seen (see collect): the
bell, the tree and the panel ask them often."""
import hashlib
import json
from dataclasses import dataclass, field

from arcadia_tool.model import discussions
from arcadia_tool.model.adr import OPEN
from arcadia_tool.model.schema import (ADR_ALLOCATION, ADR_DELETE_DOMAIN, ADR_DOMAIN_SCOPE, ADR_EXCLUSION, ADR_FUNCTION,
                                       ADR_IMPLEMENTATION, ADR_MERGE_DOMAINS, ADR_NEW_DOMAIN, ADR_OWNER,
                                       ADR_PRODUCT_OPTION, ADR_SECTION, ADR_SHARED, ADR_SPLIT_DOMAIN, KINDS_BY_NAME)
from arcadia_tool.model.teams import (design_authority, member_rows, memberships, normalize_account_id, person_key,
                                      referent_domains)

NEW, CHANGED, DELETED, MESSAGE = "Nuova", "Modificata", "Eliminata", "Messaggio"
DECISION = "Decisione DA"  # the decision of the Design Authority on an ADR, told to whom it concerns directly
READ = "Letta"  # the state of a notification opened at least once (see Notification.state)
TEAM, DA, REFERENT, MESSAGES = "team", "da", "referent", "messages"  # why a notification reaches the user
# Directed to the user in person: the ADR that impact a domain they are the referent of, the messages of the
# discussions of the ADR they proposed or of their domains, of those where they wrote, of the requests for
# clarification on the clauses of their domains.
PERSONAL = "personal"
SCOPE_LABELS = {PERSONAL: "Per me", TEAM: "Il mio team", DA: "Design Authority", REFERENT: "Referente di dominio",
                MESSAGES: "Messaggi"}
# The fields of each type naming the domains (or the teams) that receive what the ADR proposes: (field, role).
DESTINATIONS = {
    ADR_SECTION: (("primary_proposed", "dominio principale proposto"),
                  ("contributors_proposed", "contributore proposto")),
    ADR_ALLOCATION: (("primary_proposed", "dominio richiedente"),
                     ("contributors_proposed", "contributore proposto")),
    ADR_FUNCTION: (("to_domain", "dominio proposto"),),
    ADR_EXCLUSION: (("traced_by", "dominio che traccia al posto dell'escluso"),),
    ADR_SHARED: (("shared_with", "dominio con cui condividere"),
                 ("share_split", "dominio di destinazione di un sottorequisito")),
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
    ident: str = ""  # the ID of the ADR or CQ («ADR-022»)
    name: str = ""  # its title, without the ID
    kind: str = "ADR"  # what it is: «ADR», «Messaggio (ADR)», «Messaggio (CQ)»
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
                refs += [v] if isinstance(v, str) else [v.get("team"), v.get("function"), v.get("domain")]
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
        self.referent_of = referent_domains(model, user)  # the domains the user is a referent of
        self.me = person_key(getattr(user, "full_name", "") or "")

    def from_da(self, adr):
        """An ADR opened by the Design Authority reaches every member of the teams whose domains it impacts (of all
        the teams, if it impacts none, e.g. a decision across the method): [(domain or None, role)]; [] for the
        members of the DA, who opened it."""
        if not self.teams or self.is_da or not self.opened_by_da(adr) or adr.get("proposer") in self.teams:
            return []
        from arcadia_tool.model.adr import impacted_domains
        domains = impacted_domains(self.model, adr)
        if not domains:
            return [(None, "ADR della Design Authority per tutti i team")]
        return [(d, "dominio impattato da un'ADR della Design Authority") for d in domains
                if d.get("team") in self.teams]

    def directly(self, adr):
        """Whom the decision of the DA on the ADR concerns directly, for the user: (True, personal) if their team
        proposed it or has a domain it impacts, or they are the referent of one; personal: they proposed it, or are
        the referent. (False, False) for the members of the DA, who decided."""
        if self.is_da:
            return False, False
        from arcadia_tool.model.adr import impacted_domains
        mine = bool(self.me and person_key(adr.get("proposer_member") or "") == self.me)
        referent = bool(self.as_referent(adr)) if not mine else False
        team = adr.get("proposer") in self.teams or any(d.get("team") in self.teams
                                                        for d in impacted_domains(self.model, adr))
        return (team or mine or referent), (mine or referent)

    def as_referent(self, adr):
        """The domains of which the user is a referent that the ADR impacts ([(domain, role)]); [] if they proposed
        it themselves."""
        if not self.referent_of or (self.me and person_key(adr.get("proposer_member") or "") == self.me):
            return []
        from arcadia_tool.model.adr import impacted_domains
        return [(d, "dominio di cui sei referente") for d in impacted_domains(self.model, adr)
                if d.uuid in self.referent_of]

    def referent_of_clause(self, element):
        """A clause (or a section) of a domain the user is a referent of."""
        if not self.referent_of or element is None or element.kind != "requirement":
            return False
        from arcadia_tool.model.adr import item_domains
        return bool(self.referent_of & item_domains(self.model, element))

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
            "title": _title(adr), "id": adr.get("id") or "", "name": adr.get("title") or "", "relevant": relevant,
            "seen_at": discussions.now()}


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
            "noticed": dict(data.get("noticed") or {}), "opened": list(data.get("opened") or []),
            # {ADR uuid: the decision of the DA seen}; None: never worked out on this PC (the decisions there are
            # then taken as seen, not to tell at once every decision of the past)
            "decisions": dict(data["decisions"]) if isinstance(data.get("decisions"), dict) else None,
            # the decisions there when they were first worked out: not told (nor listed), unless they change
            "decisions_base": dict(data.get("decisions_base") or {})}


def _save_state(project, user, state):
    data = dict(project.local_settings().get("notifications") or {})
    data[_account(user)] = state
    project.set_local_settings(notifications=data)


def _role_text(model, roles):
    return "; ".join(f"{e.get('id') or model.label(e)} ({role})" if e is not None else role for e, role in roles)


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
    if not who.teams and not who.referent_of:
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
        by_da = who.from_da(adr)
        roles = who.roles(adr) or by_da
        da = who.as_da(adr)
        referent = who.as_referent(adr)
        scopes = frozenset(s for s, on in ((TEAM, roles), (DA, da), (REFERENT, referent),
                                           (PERSONAL, referent or by_da)) if on)
        snap = seen.get(adr.uuid)
        if not scopes and not (snap and snap.get("relevant")):
            continue
        key = f"adr:{adr.uuid}"
        version = fingerprint(adr)
        changed = snap is not None and snap.get("hash") != version
        when = snap.get("seen_at", "") if snap is not None and not changed else noticed_at(f"{key}:{version}")
        about = ("Riguarda " + _role_text(model, roles) if roles else _da_text(model, adr) if da else
                 "Impatta " + _role_text(model, referent) if referent else "")
        if snap is None:
            if adr.get("status") not in OPEN:
                continue  # received already decided: nothing to look at
            result.append(Notification(key, NEW, adr.uuid, _title(adr), about, when, True, scopes=scopes,
                                       ident=adr.get("id") or "", name=adr.get("title") or ""))
            continue
        if changed:
            fields = _changed_fields(adr, snap.get("values") or {})
            detail = ("Campi modificati: " + ", ".join(fields)) if fields else "Modificata"
            if adr.get("da_decision") != (snap.get("values") or {}).get("da_decision") and adr.get("da_decision"):
                detail = f"Decisione della DA: {adr.get('da_decision')} · {detail}"
            if not scopes:
                detail += " · non riguarda più i domini del tuo team"
        else:
            detail = about or "Non riguarda più i domini del tuo team"
        result.append(Notification(key, CHANGED if changed or not scopes else NEW, adr.uuid, _title(adr), detail,
                                   when, changed or key in forced,  # marked unread: «Nuova» again (see opened)
                                   scopes=scopes or frozenset({TEAM}),
                                   opened="hash" in snap and key not in forced,
                                   ident=adr.get("id") or "", name=adr.get("title") or ""))
    for uuid, snap in seen.items():  # ADR seen, and no longer in the project
        if uuid not in present and snap.get("relevant", True):
            key = f"adr:{uuid}"
            ident, name = snap.get("id"), snap.get("name")
            if ident is None:  # seen before the version 0.10.1: only the title with the ID is kept
                parts = (snap.get("title") or "").split(" · ", 1)
                ident, name = (parts[0], parts[1]) if len(parts) == 2 else ("", parts[0])
            result.append(Notification(key, DELETED, uuid, snap.get("title") or "ADR", "L'ADR è stata eliminata",
                                       noticed_at(f"{key}:deleted"), not snap.get("deleted_seen") or key in forced,
                                       scopes=frozenset(snap.get("scopes") or (TEAM,)),
                                       opened="hash" in snap and key not in forced, ident=ident, name=name))
    decisions = state["decisions"]
    first_time = decisions is None
    decisions = dict(decisions or {})
    base = dict(state["decisions_base"])
    told = {x.subject for x in result}  # those already told by the notification of the ADR itself
    for adr in model.of_kind("adr"):
        decision = adr.get("da_decision")
        if not decision:
            continue
        if first_time:  # the decisions already there when this PC first works them out: seen
            decisions[adr.uuid] = base[adr.uuid] = decision
            continue
        if base.get(adr.uuid) == decision:  # as it was then: nothing to tell
            continue
        concerned, personal = who.directly(adr)
        if not concerned or adr.uuid in told:
            continue
        key = f"dec:{adr.uuid}"
        new = decisions.get(adr.uuid) != decision
        result.append(Notification(key, DECISION, adr.uuid, _title(adr),
                                   f"Decisione della DA: {decision}" + (f" · {adr.get('status')}"
                                                                        if adr.get("status") else ""),
                                   noticed_at(f"{key}:{decision}"), new or key in forced,
                                   scopes=frozenset({TEAM, PERSONAL} if personal else {TEAM}),
                                   opened=not new and key not in forced,
                                   ident=adr.get("id") or "", name=adr.get("title") or ""))
    if noticed != first_noticed or first_time:
        _save_state(project, user, {**state, "noticed": noticed, "decisions": decisions, "decisions_base": base})
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
            mine = bool(who.me and person_key(subject.get("proposer_member") or "") == who.me)
            personal = mine or bool(who.as_referent(subject)) or bool(who.from_da(subject))
            concerned = (subject.get("proposer") in who.teams or who.roles(subject) or who.as_da(subject)
                         or personal)
        else:  # a request for clarification: to their teams, or about a clause of a domain they are a referent of
            personal = who.referent_of_clause(model.get(subject.get("clause") or ""))
            concerned = subject.get("recipient") in who.teams or personal
        personal = personal or uuid in wrote
        if not concerned and uuid not in wrote:
            continue
        scopes = frozenset({MESSAGES, PERSONAL} if personal else {MESSAGES})
        seen = set(read.get(uuid) or [])
        title = _title(subject) if subject.kind == "adr" else " · ".join(
            t for t in (subject.get("id"), "richiesta di chiarimento") if t)
        ident = subject.get("id") or ""
        name = subject.get("title") or subject.get("name") or ("" if subject.kind == "adr" else "Richiesta di chiarimento")
        kind = "Messaggio (ADR)" if subject.kind == "adr" else "Messaggio (CQ)"
        for m in messages:
            if discussions.is_author(m, user) or m.get("deleted"):
                continue
            text = " ".join((m.get("text") or "").split())
            start = text if len(text) <= 120 else text[:120] + "…"
            result.append(Notification(f"msg:{m.uuid}", MESSAGE, uuid, title,
                                       f"Messaggio di {m.get('author') or 'un membro'}: {start}",
                                       m.get("posted") or "", m.uuid not in seen, m.uuid,
                                       scopes=scopes, opened=m.uuid in seen,
                                       ident=ident, name=name, kind=kind))
    return result


def unread_count(project, user):
    return sum(1 for n in collect(project, user) if n.unread)


def unread_by_scope(project, user):
    """{TEAM: n, DA: n, MESSAGES: n}: the unread notifications for each reason."""
    counts = {PERSONAL: 0, TEAM: 0, DA: 0, REFERENT: 0, MESSAGES: 0}
    for n in collect(project, user):
        if n.unread:
            for scope in n.scopes:
                counts[scope] += 1
    return counts


def mark_read(project, user, notification):
    """Read: the version of the ADR now is the one seen; the message seen."""
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
    if notification.event == DECISION:  # the decision now is the one seen
        state["decisions"] = {**(state["decisions"] or {}), notification.subject: adr.get("da_decision")
                              if adr is not None else None}
        _save_state(project, user, state)
        return None
    if adr is None:  # deleted: seen
        state["adr"].setdefault(notification.subject, {})["deleted_seen"] = True
        _save_state(project, user, state)
        return None
    who = _Who(project.model, user)
    snap = _snapshot(adr, bool(who.roles(adr) or who.as_da(adr) or who.as_referent(adr) or who.from_da(adr)))
    snap["scopes"] = sorted(notification.scopes)
    state["adr"][adr.uuid] = snap
    _save_state(project, user, state)
    return None


def mark_unread(project, user, notification):
    """Unread again, «Nuova», to look at it again."""
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
