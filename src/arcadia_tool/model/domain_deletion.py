"""The ADR of the deletion of a functional domain (X-1): approved by the Design Authority, the domain is removed from
the model. What has it as its domain would be left orphan: the SRS sections and clauses of which it is principal, the
system functions, the derived requirements, the functional chains it answers for; the user says, for each, whether it
passes to another domain, stays without one, or (a function, a derived requirement nothing else uses) is deleted.
The references of second order are simply removed: the domain as a contributor or excluded, among the domains of its
team."""
from dataclasses import dataclass
from datetime import date

from arcadia_tool.model.element import natural_key
from arcadia_tool.model.schema import ADR_DELETE_DOMAIN

KEEP, DELETE = "keep", "delete"  # the choices of an orphan, besides the uuid of a domain to pass to


@dataclass(frozen=True)
class OrphanGroup:
    kind: str
    field: str
    title: str  # «Sezioni e clausole di cui è dominio principale»…
    keep: str  # what «keep» means for these elements
    deletable: bool  # its elements can be deleted (when nothing else uses them)


GROUPS = (
    OrphanGroup("requirement", "primary_domain", "Sezioni e clausole SRS di cui è dominio principale",
                "Senza dominio principale", False),
    OrphanGroup("system_function", "domain", "Funzioni di sistema", "Senza dominio", True),
    OrphanGroup("derived_requirement", "domain", "Requisiti derivati", "Senza dominio", True),
    OrphanGroup("functional_chain", "responsible_domain", "Functional chain di cui è responsabile",
                "Senza dominio responsabile", False),
)


def deleted_domain(model, adr):
    """The domain the ADR deletes, if it is still in the model."""
    uuid = adr.get("deleted_domain")
    domain = model.get(uuid) if uuid else None
    return domain if domain is not None and domain.kind == "domain" else None


def deletion_problems(model, adr):
    """What is missing to approve the deletion (empty list: it can be approved)."""
    if adr.get("adr_type") != ADR_DELETE_DOMAIN:
        return ["L'ADR non è di eliminazione di un dominio."]
    if not adr.get("deleted_domain"):
        return ["Manca il dominio da eliminare."]
    if deleted_domain(model, adr) is None:
        return ["Il dominio da eliminare non è più nel modello."]
    return []


def orphans(model, domain_uuid):
    """The elements left without their domain if it is deleted: [(OrphanGroup, [elements])], the groups with some, the
    elements by their ID (or name)."""
    result = []
    for group in GROUPS:
        found = sorted((e for e in model.of_kind(group.kind) if e.get(group.field) == domain_uuid),
                       key=lambda e: natural_key(e.get("id") or e.get("name") or ""))
        if found:
            result.append((group, found))
    return result


def second_references(model, domain_uuid):
    """The elements that only lose a mention of the domain (as a contributor, as excluded, among the domains of a
    team): the reference is removed."""
    return [e for e in model.of_kind("requirement", "team")
            if domain_uuid in (e.get("contributing_domains") or []) + (e.get("excluded_domains") or [])
            + (e.get("domains") or [])]


def deletable(model, element, domain_uuid):
    """An orphan that can be deleted: of a kind that can, and used by no other element (but the domain itself and
    the ADR, which only name it)."""
    group = next(g for g in GROUPS if g.kind == element.kind)
    if not group.deletable:
        return False
    return not [e for e in model.referencing([element.uuid]) if e.uuid != domain_uuid and e.kind not in ("adr",)]


def approve_domain_deletion(project, adr, choices=None, today=None):
    """The Design Authority approves the deletion: each orphan as chosen ({uuid: KEEP, DELETE or the uuid of another
    domain}; KEEP if not said), the mentions of the domain removed, the domain deleted; the ADR decided, with the
    name of the domain it deleted (its reference no longer leads anywhere). Returns (elements changed, uuids
    deleted)."""
    from arcadia_tool.model.adr import DECIDED, decision_date_of

    problems = deletion_problems(project.model, adr)
    if problems:
        raise ValueError(" ".join(problems))
    model, choices = project.model, choices or {}
    domain = deleted_domain(model, adr)
    changed, deleted = {}, []
    for group, elements in orphans(model, domain.uuid):
        for element in elements:
            choice = choices.get(element.uuid, KEEP)
            if choice == DELETE and deletable(model, element, domain.uuid):
                project.delete_element(element.uuid)
                deleted.append(element.uuid)
                continue
            target = choice if choice not in (KEEP, DELETE) and model.get(choice) is not None else None
            previous = element.copy()
            element.set(group.field, target)
            if group.kind == "requirement" and target:  # principal: no longer a contributor of it
                element.set("contributing_domains", [d for d in element.get("contributing_domains") or []
                                                     if d != target])
            for other in [element, *(project.update(element, previous) or [])]:
                changed[other.uuid] = other
    for element in second_references(model, domain.uuid):
        previous = element.copy()
        for name in ("contributing_domains", "excluded_domains", "domains"):
            if domain.uuid in (element.get(name) or []):
                element.set(name, [d for d in element.get(name) if d != domain.uuid])
        for other in [element, *(project.update(element, previous) or [])]:
            changed[other.uuid] = other
    previous = adr.copy()
    adr.set("deleted_domain_label", model.label(domain))
    adr.set("status", DECIDED)
    if adr.get("da_decision") not in ("Accolta", "Accolta con modifiche"):
        adr.set("da_decision", "Accolta")
    adr.set("decision_date", decision_date_of(adr, today=today))
    project.update(adr, previous)
    project.delete_element(domain.uuid)
    deleted.append(domain.uuid)
    return [e for u, e in changed.items() if model.get(u) is not None], deleted
