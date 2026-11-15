"""The interfaces between the domains, from the functional exchanges of the model (generated, never stored).

- The state of an exchange as the teams see it: agreed («Concordato», «Approvato»), still to agree (proposed, or no
  state), and whether its datum is defined (an Exchange Item) or still to define.
- The N² matrix: a row for each producer, a column for each user (the functional domains, then the external
  actors), in each cell the exchanges from the one to the other; on the diagonal the exchanges inside a domain."""
from dataclasses import dataclass, field

from arcadia_tool.model.chains import domain_of
from arcadia_tool.model.element import natural_key

AGREED = ("Concordato", "Approvato")
TO_AGREE = "da concordare"
UNDEFINED = "(dato da definire)"


def agreed(fe):
    return (fe.get("status") or "") in AGREED


def has_data(model, fe):
    return model.get(fe.get("exchange_item") or "") is not None


def datum(model, fe):
    """The datum of the exchange: its Exchange Item (its ID), else the mark of a datum still to define."""
    item = model.get(fe.get("exchange_item") or "")
    if item is None:
        return UNDEFINED
    return item.get("id") or item.get("name") or UNDEFINED


@dataclass
class Cell:
    exchanges: list = field(default_factory=list)  # the functional exchanges (elements)

    @property
    def count(self):
        return len(self.exchanges)


@dataclass
class Matrix:
    ends: list = field(default_factory=list)  # the domains, then the external actors (elements)
    cells: dict = field(default_factory=dict)  # {(producer uuid, user uuid): Cell}
    without_domain: int = 0  # exchanges of a function without a domain: not in the matrix

    def cell(self, source, target):
        return self.cells.get((source, target))


def end_of(model, uuid):
    """The row or column of an end of an exchange: the domain of a function (also logical), or the actor."""
    e = model.get(uuid) if uuid else None
    if e is None:
        return None
    if e.kind == "external_actor":
        return e
    return domain_of(model, e.uuid)


def interface_matrix(model):
    result = Matrix()
    domains = sorted(model.of_kind("domain"), key=lambda d: natural_key(d.get("id") or d.get("name") or ""))
    actors = sorted(model.of_kind("external_actor"), key=lambda a: natural_key(a.get("id") or a.get("name") or ""))
    used = set()
    for fe in model.of_kind("functional_exchange"):
        source, target = end_of(model, fe.get("source")), end_of(model, fe.get("target"))
        if source is None or target is None:
            result.without_domain += 1
            continue
        result.cells.setdefault((source.uuid, target.uuid), Cell()).exchanges.append(fe)
        used |= {source.uuid, target.uuid}
    for cell in result.cells.values():
        cell.exchanges.sort(key=lambda fe: natural_key(fe.get("id") or ""))
    # Every domain (an empty row shows a domain still isolated); the actors only when they exchange something.
    result.ends = domains + [a for a in actors if a.uuid in used]
    return result


def summary(matrix):
    """(interfaces between two different ends, exchanges, to agree, without a datum) of the matrix."""
    interfaces = sum(1 for (s, t) in matrix.cells if s != t)
    exchanges = [fe for c in matrix.cells.values() for fe in c.exchanges]
    return (interfaces, len(exchanges), sum(1 for fe in exchanges if not agreed(fe)),
            sum(1 for fe in exchanges if not fe.get("exchange_item")))
