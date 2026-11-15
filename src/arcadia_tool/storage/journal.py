"""The local changes in the order they were made: each action of the user (a sheet saved, an element created or
deleted, a view changed…) is an entry with the elements it changed, as they were and as they became. Any entry can be
discarded (its elements back as they were) with the later ones linked to it, which could not stay without it; a
discarded entry can be restored with the earlier discarded ones it needs. Two entries are linked when they change the
same element, when one refers to an element the other creates or deletes, or when they give the same identifier to
different elements (e.g. DF02 given again after DF02 was deleted).

The entries cover the changes not yet published of the branch: the file (.arcadia/local_changes.json, not
published) is written with the project and read when it is opened, if it still fits the project (the same last
version, the elements as the entries leave them); else it starts again. The changes made before the entries (in an
earlier version of ATLAS, or before a version was received) are one first entry, «Modifiche precedenti»: from the last
version published to the state before the first entry.

The state before an entry is not taken when an element changes (the sheets change the element and then tell the
project) but from a «shadow»: the elements as the last entry left them, or as they are saved on disk."""
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from arcadia_tool.model.schema import KINDS_BY_NAME
from arcadia_tool.model.serialization import dumps, loads
from arcadia_tool.storage.repository import MODEL_DIR

JOURNAL_NAME = ".arcadia/local_changes.json"
BASELINE_LABEL = "Modifiche precedenti"


@dataclass
class Change:
    """One element in an entry: before and after are its text (as in its file), None when it did not exist."""
    uuid: str
    kind: str
    label: str
    before: str | None
    after: str | None

    @property
    def what(self):
        return "added" if self.before is None else "removed" if self.after is None else "modified"


@dataclass
class Entry:
    time: str  # ISO, to the second
    label: str
    changes: list = field(default_factory=list)
    undone: bool = False  # discarded: it can be restored
    baseline: bool = False  # «Modifiche precedenti»: the changes made before the entries
    undone_order: int = 0  # when it was discarded (the last discarded: the highest)

    def to_json(self):
        return {"time": self.time, "label": self.label, "undone": self.undone, "baseline": self.baseline,
                "undone_order": self.undone_order, "changes": [vars(c) for c in self.changes]}

    @classmethod
    def from_json(cls, data):
        return cls(data["time"], data["label"], [Change(**c) for c in data["changes"]], data.get("undone", False),
                   data.get("baseline", False), data.get("undone_order", 0))

    @property
    def uuids(self):
        return {c.uuid for c in self.changes}


ID_LINE = re.compile(r"^id: *['\"]?([^'\"\n]+?)['\"]? *$", re.MULTILINE)


def _ids(entry):
    """{identifier: the uuids that have it} in the texts of the entry."""
    found = {}
    for c in entry.changes:
        for text in (c.before, c.after):
            for ident in ID_LINE.findall(text or ""):
                found.setdefault(ident, set()).add(c.uuid)
    return found


def linked(a, b):
    """The two entries cannot be discarded or restored one without the other (see the module)."""
    if a.uuids & b.uuids:
        return True
    for x, y in ((a, b), (b, a)):
        born_or_gone = [c.uuid for c in x.changes if c.before is None or c.after is None]
        texts = [t for c in y.changes for t in (c.before, c.after) if t]
        if any(u in t for u in born_or_gone for t in texts):
            return True
    ids_a, ids_b = _ids(a), _ids(b)
    return any(ids_a[i] != ids_b[i] for i in ids_a.keys() & ids_b.keys())


def _values(text):
    return None if text is None else loads(text).values


def _same(text, element):
    """The element (None: absent) is as the text says."""
    if text is None or element is None:
        return text is None and element is None
    return loads(text).values == element.values


class Journal:
    def __init__(self, project):
        self.project = project
        self.entries = []
        self.head = project.repository.head()
        self._shadow = {}  # {uuid: text or None}: as the last entry left it (else: as saved)
        self._mark = project.change_mark()

    # --- the file ------------------------------------------------------------------------------------------------

    @property
    def file(self):
        return Path(self.project.path) / JOURNAL_NAME

    def load(self):
        """The entries of the file, if they still fit the project; else none."""
        try:
            data = json.loads(self.file.read_text(encoding="utf-8"))
            entries = [Entry.from_json(e) for e in data.get("entries", [])]
        except (OSError, ValueError, KeyError, TypeError):
            return
        if data.get("head") != self.project.repository.head() or not self._fits(entries):
            return
        self.entries = entries

    def _fits(self, entries):
        """The model is as the entries leave it: each element as the last entry done made it, or as the first one
        discarded expects it."""
        expected = {}
        for entry in entries:
            for c in entry.changes:
                if not entry.undone:
                    expected[c.uuid] = c.after
                else:
                    expected.setdefault(c.uuid, c.before)
        model = self.project.model
        try:
            return all(_same(text, model.get(uuid)) for uuid, text in expected.items())
        except Exception:  # a text that no longer reads (e.g. a kind removed)
            return False

    def write(self):
        """With the project saved (see Project.save): the entries for the next opening."""
        self.check_head()
        if not self.entries:
            self.file.unlink(missing_ok=True)
            return
        self.file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.file.with_name(self.file.name + ".tmp")
        tmp.write_text(json.dumps({"head": self.head, "entries": [e.to_json() for e in self.entries]},
                                  ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.file)

    def clear(self):
        """The changes published, discarded or replaced: no entry left."""
        self.entries = []
        self.head = self.project.repository.head()
        self.file.unlink(missing_ok=True)

    def check_head(self):
        """A version published or received meanwhile: the entries were about the version before, they go (what is
        still local is in «Modifiche precedenti», see add_baseline)."""
        head = self.project.repository.head()
        if head != self.head:
            self.entries = []
            self.head = head

    # --- recording -----------------------------------------------------------------------------------------------

    def _before(self, uuid):
        if uuid in self._shadow:
            return self._shadow[uuid]
        return self.project.saved_text(uuid)

    def record(self, label=None):
        """The elements changed since the last entry, as one entry (the action of the user just ended). None if
        nothing changed."""
        project = self.project
        mark = project.change_mark()
        if mark == self._mark:
            return None
        touched = sorted((n, u) for u, n in project._stamps.items() if n > self._mark)
        self._mark = mark
        changes = []
        for _n, uuid in touched:
            element = project.model.get(uuid)
            before = self._before(uuid)
            after = dumps(element) if element is not None else None
            if before == after or (before is not None and element is not None and _same(before, element)):
                self._shadow[uuid] = after
                continue
            source = element if element is not None else loads(before)
            changes.append(Change(uuid, source.kind, project.model.label(source), before, after))
            self._shadow[uuid] = after
        if not changes:
            return None
        self.check_head()
        entry = Entry(datetime.now().isoformat(timespec="seconds"), label or describe(changes), changes)
        # The entries discarded linked to it can no longer be restored (with the later ones that need them): they
        # stay discarded, and leave the list.
        dropped = []
        for e in self.entries:
            if e.undone and (linked(entry, e) or any(linked(e, d) for d in dropped)):
                dropped.append(e)
        self.entries = [e for e in self.entries if not any(e is d for d in dropped)]
        self.entries.append(entry)
        return entry

    # --- discarding and restoring, one at a time -----------------------------------------------------------------

    def last_done(self):
        return next((e for e in reversed(self.entries) if not e.undone), None)

    def last_undone(self):
        """The entry discarded last (of those discarded together, the latest)."""
        undone = [e for e in self.entries if e.undone]
        return max(undone, key=lambda e: (e.undone_order, self.entries.index(e))) if undone else None

    def to_undo(self, entry):
        """The entries discarded with it: it, and the later ones in force linked to it (and to them)."""
        start = self._index(entry)
        group = [entry]
        for e in self.entries[start + 1:]:
            if not e.undone and any(linked(e, g) for g in group):
                group.append(e)
        return group

    def to_redo(self, entry):
        """The entries restored with it: it, and the earlier discarded ones it is linked to (and they)."""
        start = self._index(entry)
        group = [entry]
        for e in reversed(self.entries[:start]):
            if e.undone and any(linked(e, g) for g in group):
                group.append(e)
        return sorted(group, key=self._index)

    def _index(self, entry):
        return next(i for i, e in enumerate(self.entries) if e is entry)

    def undo(self, entry=None):
        """The entry (else the last one in force) and those linked to it: their elements back as they were.
        Returns them (empty if there is none)."""
        self.record()  # anything changed and not recorded yet: an entry of its own, first
        entry = entry or self.last_done()
        if entry is None or entry.undone:
            return []
        group = self.to_undo(entry)
        self._apply(sorted(group, key=self._index, reverse=True), undo=True)
        order = max((e.undone_order for e in self.entries), default=0) + 1
        for e in group:
            e.undone, e.undone_order = True, order
        return group

    def redo(self, entry=None):
        """The entry discarded (else the last one discarded) and the earlier discarded ones it needs: their elements
        as they had made them. Returns them."""
        self.record()
        entry = entry or self.last_undone()
        if entry is None or not entry.undone:
            return []
        group = self.to_redo(entry)
        self._apply(group, undo=False)
        for e in group:
            e.undone, e.undone_order = False, 0
        return group

    def _apply(self, group, undo):
        """The entries of the group, in the order given (undo: the latest first), each element as it was before (or
        after) them. First checked: every element is as the group expects it."""
        model = self.project.model
        expected = {}
        for e in group:
            for c in e.changes:
                expected.setdefault(c.uuid, (c.after if undo else c.before, c.label))
        for uuid, (text, label) in expected.items():
            if not _same(text, model.get(uuid)):
                raise JournalError(f"«{label}» è stato cambiato in un altro modo: la modifica non si può più "
                                   f"{'scartare' if undo else 'ripristinare'} da qui.")
        for e in group:
            for c in e.changes:
                text = c.before if undo else c.after
                self.project.put_text(c.uuid, text)
                self._shadow[c.uuid] = text
        self._mark = self.project.change_mark()

    # --- the changes before the entries --------------------------------------------------------------------------

    def add_baseline(self):
        """«Modifiche precedenti»: from the last version published to the state before the first entry, as the first
        entry (once). Nothing published yet: none (there is no version to go back to)."""
        self.record()
        self.check_head()
        if not self.head or any(e.baseline for e in self.entries):
            return None
        project = self.project
        published = {}
        for path, data in project.repository.files_at(self.head).items():
            if path.startswith(MODEL_DIR + "/") and path.endswith(".yaml"):
                published[path.rsplit("/", 1)[-1][:-5]] = data.decode("utf-8")
        start = {}  # the state before the first entry, of the elements the entries changed
        for entry in self.entries:
            for c in entry.changes:
                start.setdefault(c.uuid, c.before)
        changes = []
        for uuid in sorted(set(published) | set(project.model.elements) | set(start)):
            if uuid in start:
                text = start[uuid]
            else:
                element = project.model.get(uuid)
                text = None if element is None else project.saved_text(uuid, element) if (
                    uuid not in project.pending()) else dumps(element)
            old = published.get(uuid)
            if old == text or (old is not None and text is not None and _values(old) == _values(text)):
                continue
            source = loads(text if text is not None else old)
            changes.append(Change(uuid, source.kind, project.model.label(source), old, text))
        if not changes:
            return None
        entry = Entry(self.entries[0].time if self.entries else datetime.now().isoformat(timespec="seconds"),
                      BASELINE_LABEL, changes, baseline=True)
        self.entries.insert(0, entry)
        return entry


class JournalError(Exception):
    pass


VERBS = {"added": "Creato", "removed": "Eliminato", "modified": "Modificato"}


def describe(changes):
    """The label of an entry: what happened to its first element, and how many others changed with it."""
    first = changes[0]
    kind = KINDS_BY_NAME[first.kind].label if first.kind in KINDS_BY_NAME else first.kind
    text = f"{VERBS[first.what]} {kind} «{first.label}»"
    others = len(changes) - 1
    if others:
        text += f" e {'un altro elemento' if others == 1 else f'altri {others} elementi'}"
    return text
