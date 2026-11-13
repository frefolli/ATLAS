"""Links between SRS items: a clause that refers to another one («Richiama»: see 3.5.3.7), includes it («Include»:
its content is part of the clause), or depends on it («Dipende da»: it needs what the other one says or does). Kept
in the item that links («links»: rows {type, target}), an analysis datum like its domains; the other way («Richiamata
da», «Inclusa in», «Necessaria a») is worked out.

What they change: a clause that includes others is covered, for the part included, by their tracing (the SA-3
outcome «Coperta dalla clausola inclusa», the coverage, the functions traced to it); referring and depending are said
only (a clause referring to, or depending on, one of another domain: an exchange between the two domains to look at,
see check A4-11)."""

REFERS, INCLUDES, DEPENDS = "Richiama", "Include", "Dipende da"
LINK_TYPES = (REFERS, INCLUDES, DEPENDS)
INVERSE = {REFERS: "Richiamata da", INCLUDES: "Inclusa in", DEPENDS: "Necessaria a"}
COVERED_BY_INCLUDED = "Coperta dalla clausola inclusa"  # the SA-3 outcome of a clause including others


def links_of(item):
    """The links of an SRS item: [(type, target uuid)], in their order."""
    return [(row.get("type"), row.get("target")) for row in item.get("links") or []
            if isinstance(row, dict) and row.get("type") in LINK_TYPES and row.get("target")]


def link_rows(links):
    """The rows kept in the item for [(type, target uuid)], each once."""
    return [{"type": t, "target": u} for t, u in dict.fromkeys(links)]


def incoming(model, item_uuid):
    """The links to an SRS item from the others: [(type, source item)], by the number of the source."""
    from arcadia_tool.model.element import natural_key

    found = [(t, e) for e in model.of_kind("requirement") for t, u in links_of(e) if u == item_uuid]
    return sorted(found, key=lambda x: (natural_key(x[1].get("id") or ""), LINK_TYPES.index(x[0])))


def included(model, item_uuid):
    """The SRS items an item includes, directly or through the items they include (each once, no loops)."""
    found, todo, seen = [], [item_uuid], {item_uuid}
    while todo:
        item = model.get(todo.pop(0))
        if item is None:
            continue
        for link_type, target in links_of(item):
            if link_type == INCLUDES and target not in seen:
                seen.add(target)
                found.append(target)
                todo.append(target)
    return found


def includes_loop(model, item_uuid):
    """The item includes itself, through the items it includes."""
    item = model.get(item_uuid)
    if item is None:
        return False
    todo = [u for t, u in links_of(item) if t == INCLUDES]
    seen = set()
    while todo:
        uuid = todo.pop()
        if uuid == item_uuid:
            return True
        if uuid in seen or model.get(uuid) is None:
            continue
        seen.add(uuid)
        todo += [u for t, u in links_of(model.get(uuid)) if t == INCLUDES]
    return False
