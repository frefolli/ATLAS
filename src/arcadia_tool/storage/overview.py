"""The overview of the branches: the main branch (what is approved) with what the other branches propose on top of it,
computed in memory from their versions. Nothing is written: no version, no file, no merge.

What a branch proposes is what it has changed since it left the main branch (the last version they have in common)
and the main branch does not have yet. A branch left behind therefore proposes nothing about what the main branch has
approved after it left, and what has been integrated becomes approved by itself, its values being those of the main
branch.

The values of the branches are kept side by side, never merged into one: which one wins would depend on the order of
the branches."""
import json
from dataclasses import dataclass, field

from arcadia_tool.model.element import Model, is_empty
from arcadia_tool.model.schema import REFS
from arcadia_tool.storage.selective import references

APPROVED, CHANGED, NEW, REMOVED, DIVERGENT = "approved", "changed", "new", "removed", "divergent"
STATES = (APPROVED, CHANGED, NEW, REMOVED, DIVERGENT)
STATE_LABELS = {APPROVED: "Approvato", CHANGED: "Modificato", NEW: "Nuovo", REMOVED: "Rimosso", DIVERGENT: "Divergente"}
# Not elements of their own in the view: the messages are in the sheet of their ADR or CQ, the readings are no more.
NOT_SHOWN = ("message", "reading")


@dataclass(frozen=True)
class Source:
    """A branch as it enters the view: its last version sent to the repository, or of this PC if never sent."""
    name: str
    sha: str
    only_here: bool = False  # never sent to the repository
    differs: bool = False  # this PC has another version of it, not used here


@dataclass
class Proposal:
    branch: str
    element: object = None  # the element on the branch; None if removed
    fields: dict = field(default_factory=dict)  # {field: the value proposed} (None: emptied)

    @property
    def removed(self):
        return self.element is None


@dataclass
class Entry:
    uuid: str
    kind: str
    approved: object = None  # the element in the main branch, or None
    proposals: list = field(default_factory=list)

    @property
    def element(self):
        """The element to name it by: as approved, or as on the first branch."""
        return self.approved if self.approved is not None else self.proposals[0].element

    @property
    def branches(self):
        return [p.branch for p in self.proposals]

    @property
    def divergent_fields(self):
        """The fields on which the branches propose different values."""
        proposing = [p for p in self.proposals if not p.removed]
        names = dict.fromkeys(n for p in proposing for n in p.fields)
        found = []
        for name in names:
            # On an element already approved, a branch that does not name the field has left it alone.
            values = [p.fields.get(name) for p in proposing if self.approved is None or name in p.fields]
            if len({_key(v) for v in values}) > 1:
                found.append(name)
        return found

    @property
    def state(self):
        if not self.proposals:
            return APPROVED
        removals = sum(p.removed for p in self.proposals)
        if removals:
            return REMOVED if removals == len(self.proposals) else DIVERGENT
        if self.divergent_fields:
            return DIVERGENT
        return NEW if self.approved is None else CHANGED


@dataclass
class Overview:
    main: Source
    branches: list  # the Sources overlaid
    entries: dict  # {uuid: Entry}
    excluded: list = field(default_factory=list)  # (Source, why it could not be overlaid)
    model: Model = field(default_factory=Model)  # to name the elements: as approved, else as on the branches

    def label_of(self, uuid):
        return self.model.label_of(uuid) or "(elemento non disponibile)"

    def shown(self):
        """The entries that are elements of the view."""
        return [e for e in self.entries.values() if e.kind not in NOT_SHOWN]

    def messages_of(self, uuid):
        """The entries of the messages of the discussion of an ADR or a CQ, from all the branches, the oldest first."""
        found = [e for e in self.entries.values() if e.kind == "message" and e.element is not None
                 and e.element.get("subject") == uuid]
        return sorted(found, key=lambda e: (e.element.get("posted") or "", e.uuid))

    def linked(self, uuids):
        """The elements the elements `uuids` directly refer to, in the version approved or on a branch."""
        known = self.entries.keys()
        found = set()
        for uuid in uuids:
            entry = self.entries.get(uuid)
            if entry is None:
                continue
            versions = [entry.approved] + [p.element for p in entry.proposals]
            for version in versions:
                if version is not None:
                    found |= references(version, known)
        return {u for u in found if self.entries[u].kind not in NOT_SHOWN}


def _key(value, as_set=False):
    value = None if is_empty(value) else value
    if as_set and isinstance(value, list):
        value = sorted(value, key=str)
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)


def _applied(approved, before, after):
    """A list of references as approved, with what the branch has added to it and removed from it."""
    approved, before, after = approved or [], before or [], after or []
    removed = set(before) - set(after)
    added = [v for v in after if v not in before and v not in approved]
    return [v for v in approved if v not in removed] + added


def proposal(branch, before, after, approved):
    """What the branch proposes about an element it has changed, or None. before, after: the element where the branch
    left the main branch and on the branch (None: it was not there); approved: in the main branch now."""
    if after is None:
        return Proposal(branch) if approved is not None else None
    if approved is None:
        return Proposal(branch, after, {n: v for n, v in after.values.items() if not is_empty(v)})
    old = before.values if before is not None else {}
    fields = {}
    for name in dict.fromkeys([*old, *after.values]):
        if name == "id" and before is None:
            continue  # new on the branch and already integrated: the main branch may have given it another number
        schema = after.schema.field(name)
        as_set = schema is not None and schema.type == REFS
        a, b, m = after.values.get(name), old.get(name), approved.values.get(name)
        if _key(a, as_set) == _key(b, as_set):
            continue
        value = _applied(m, b, a) if as_set else a
        if _key(value, as_set) != _key(m, as_set):
            fields[name] = value
    return Proposal(branch, after, fields) if fields else None


class OverviewBuilder:
    """Computes overviews, keeping what it has read: choosing other branches reads nothing again, and only the
    elements that differ are read at all."""

    def __init__(self, repository):
        self.repository = repository
        self._blobs, self._elements, self._bases = {}, {}, {}

    def _blobs_at(self, sha):
        if sha not in self._blobs:
            self._blobs[sha] = self.repository.model_blobs(sha)
        return self._blobs[sha]

    def _element(self, blob):
        if blob is None:
            return None
        if blob not in self._elements:
            self._elements[blob] = self.repository.element_of_blob(blob)
        return self._elements[blob]

    def _base(self, a, b):
        if (a, b) not in self._bases:
            self._bases[a, b] = self.repository.merge_base(a, b)
        return self._bases[a, b]

    def build(self, main, sources):
        """The Overview of the Source `main` with the Sources `sources` overlaid."""
        main_blobs = self._blobs_at(main.sha)
        entries = {}
        for uuid, blob in main_blobs.items():
            element = self._element(blob)
            entries[uuid] = Entry(uuid, element.kind, element)
        excluded, overlaid = [], []
        for source in sources:
            base = self._base(main.sha, source.sha)
            if base is None:
                excluded.append((source, "non ha versioni in comune con il ramo principale"))
                continue
            overlaid.append(source)
            before, after = self._blobs_at(base), self._blobs_at(source.sha)
            for uuid in sorted(set(before) | set(after)):
                if before.get(uuid) == after.get(uuid):
                    continue
                entry = entries.get(uuid)
                found = proposal(source.name, self._element(before.get(uuid)), self._element(after.get(uuid)),
                                 entry.approved if entry is not None else None)
                if found is not None:
                    if entry is None:
                        entry = entries[uuid] = Entry(uuid, found.element.kind)
                    entry.proposals.append(found)
        model = Model(e.element for e in entries.values())
        return Overview(main, overlaid, entries, excluded, model)
