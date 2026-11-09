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


# --- integrating some elements of another branch --------------------------------------------------------------------

class Selection:
    """What can be taken from a branch: diff: the branch in use → as it would be, only with what the other branch has
    changed; needs: {uuid: the changes linked to it, which come with it}; blocked: {uuid of a removal: the elements of
    the branch in use that still refer to it}; here: the model of the branch in use."""

    def __init__(self, diff, needs, blocked, here):
        self.diff, self.needs, self.blocked, self.here = diff, needs, blocked, here


def _linked(base, here, there, changed):
    """{uuid of a change: the changes that come with it}. What an element refers to, if changed too: but not an SRS item
    only changed, unless a reallocation applied moved it (its decision and its effect go together). The messages and
    readings of an ADR or a CQ, and the SA-3 record of a derived requirement, follow it."""
    known = set(base.elements) | set(here.elements) | set(there.elements)
    needs = {u: set() for u in changed}
    referring = {}
    for e in base.elements.values():
        for r in references(e, known):
            referring.setdefault(r, set()).add(e.uuid)
    for uuid in changed:
        now = there.get(uuid)
        if now is None:  # removed: the changes of the elements that referred to it
            needs[uuid] |= {e for e in referring.get(uuid, ()) if e in changed}
            continue
        applied = now.kind == "adr" and now.get("realloc_applied")
        for r in references(now, known):
            target = there.get(r)
            if r not in changed or target is None:
                continue
            if target.kind != "requirement" or here.get(r) is None or applied:
                needs[uuid].add(r)
    for e in there.elements.values():
        if e.uuid not in changed:
            continue
        if e.kind in ("message", "reading"):
            for owner in (e.get("subject"), e.get("adr")):
                if owner in needs:
                    needs[owner].add(e.uuid)
        elif e.kind == "trace_record":
            for d in there.of_kind("derived_requirement"):
                if d.uuid in needs and d.get("parent") == e.get("requirement"):
                    needs[d.uuid].add(e.uuid)
    return needs


def integration_selection(base, ours, theirs):
    """The Selection of an integration; base, ours, theirs: {path: bytes} (the last version in common, the branch in
    use, the other branch). Only what the other branch has changed, and the branch in use does not have yet."""
    from arcadia_tool.diff.semantic import diff_models
    from arcadia_tool.storage.merge import THEIRS, merge_files, merged_model

    model_paths = [p for p in set(base) | set(theirs) if p.startswith(MODEL_DIR + "/") and p.endswith(".yaml")]
    changed = {_uuid_of(p) for p in model_paths if theirs.get(p) != base.get(p) and theirs.get(p) != ours.get(p)}
    limited = selected_files(base, theirs, changed)
    conflicts = merge_files(base, ours, limited).conflicts
    merged = merge_files(base, ours, limited, {c.key: THEIRS for c in conflicts})  # the conflicts: as they would be
    here, there = merged_model(ours), merged_model(theirs)
    diff = diff_models(here, merged_model(merged.files))
    diff.changes = [c for c in diff.changes if c.uuid in changed]
    shown = {c.uuid for c in diff.changes}
    needs = {u: linked & shown for u, linked in _linked(merged_model(base), here, there, shown).items()}
    known = set(here.elements)
    blocked = {}
    for uuid in shown:
        if there.get(uuid) is None:  # still used here by something not changing: it cannot go away
            users = [e for e in here.elements.values() if e.uuid != uuid and e.uuid not in shown
                     and uuid in references(e, known)]
            if users:
                blocked[uuid] = sorted(here.label(e) for e in users)
    return Selection(diff, needs, blocked, here)


def selected_files(base, theirs, chosen):
    """The content of the other branch as if it had changed only the elements chosen (uuids), with their files: the
    rest as in the last version in common, so that the merge leaves it as it is in the branch in use."""
    from arcadia_tool.model.serialization import loads

    result = dict(base)
    for path in set(base) | set(theirs):
        if path.startswith(MODEL_DIR + "/") and path.endswith(".yaml") and _uuid_of(path) in chosen:
            if path in theirs:
                result[path] = theirs[path]
                element = loads(theirs[path].decode("utf-8"))
                for name in ASSET_FIELDS:
                    value = element.values.get(name)
                    for asset in (value if isinstance(value, list) else [value] if value else []):
                        if asset in theirs:
                            result[asset] = theirs[asset]
            else:
                result.pop(path, None)
    return result

