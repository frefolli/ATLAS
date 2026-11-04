"""Publishing some of the changes only: the changes of the model (an element added, changed or removed) depend on one
another through their references, and are published together so that the version published has no reference to an
element it does not have.

- An element added or changed that refers to an element added: it needs that element (published with it).
- An element removed: it needs the changes of the elements that referred to it in the last version (they no longer
  do, or they are removed too): else the version would still refer to it.

Leaving a change out leaves out the changes that need it; choosing one chooses those it needs. What is not
published stays as a local change, to publish later."""
from arcadia_tool.storage.repository import MODEL_DIR

ASSET_FIELDS = ("figure", "attachments")  # the fields naming the files of the project (assets/…)


def references(element, known):
    """The uuids of the elements the element refers to: any value (also in tables and lists) that is the uuid of
    an element of `known` (the elements of the two states)."""
    found = set()

    def walk(value):
        if isinstance(value, str):
            if value in known and value != element.uuid:
                found.add(value)
        elif isinstance(value, dict):
            for v in value.values():
                walk(v)
        elif isinstance(value, (list, tuple)):
            for v in value:
                walk(v)

    walk(element.values)
    return found


def dependencies(before, after, changed):
    """{uuid of a change: the uuids of the changes it needs}. before: the model published, after: the model now,
    changed: the uuids of the elements changed (added, changed, removed)."""
    changed = set(changed)
    known = set(before.elements) | set(after.elements)
    needs = {u: set() for u in changed}
    referring = {}  # in the version published: element → the elements referring to it
    for e in before.elements.values():
        for r in references(e, known):
            referring.setdefault(r, set()).add(e.uuid)
    for uuid in changed:
        now = after.get(uuid)
        if now is not None:  # added or changed: the elements added it refers to
            needs[uuid] |= {r for r in references(now, known) if r in changed and before.get(r) is None}
        else:  # removed: the changes of the elements that referred to it
            needs[uuid] |= {e for e in referring.get(uuid, ()) if e in changed}
    return needs


def required(needs, uuids):
    """The changes and all those they need, transitively."""
    result, todo = set(), list(uuids)
    while todo:
        u = todo.pop()
        if u not in result:
            result.add(u)
            todo += needs.get(u, ())
    return result


def dependents(needs, uuids):
    """The changes and all those that need them, transitively."""
    users = {}
    for u, required_ in needs.items():
        for r in required_:
            users.setdefault(r, set()).add(u)
    return required(users, uuids)


def files_to_publish(base, working, before, after, chosen, settings, tracked):
    """The project content of the version: the last one (base, {path: bytes}) with the changes chosen (uuids) taken
    from the content now (working); the settings files (tracked) of now if settings, else of the last version; the
    files of the project (assets) used by the elements of the version, as they are now."""
    result = {p: d for p, d in base.items() if not p.startswith(MODEL_DIR + "/") or not _uuid_of(p) in chosen}
    for path, data in working.items():
        if path.startswith(MODEL_DIR + "/") and _uuid_of(path) in chosen:
            result[path] = data  # changed or added (a removed one is no longer in working)
    for name in tracked:
        source = working if settings else base
        if name in source:
            result[name] = source[name]
        else:
            result.pop(name, None)
    used = set()
    for uuid in set(before.elements) | set(after.elements):
        element = (after if uuid in chosen else before).get(uuid)
        if element is not None:
            for name in ASSET_FIELDS:
                value = element.values.get(name)
                used |= set(value) if isinstance(value, list) else {value} if value else set()
    for path in [p for p in result if p.startswith("assets/")]:
        if path not in used:
            del result[path]
    for path in used:
        if path in working:
            result[path] = working[path]
        elif path in base:
            result[path] = base[path]
    return result


def _uuid_of(path):
    return path.rsplit("/", 1)[-1].removesuffix(".yaml")
