"""The values of a functional chain (SA-7) and of an exchange item (SA-6) computed from the model: the columns of the
path read from the function of the step, the domains involved, the exchanges used, the producers and the users of a
data item. Shown read-only in their sheets and written in the documents. And the changes of the path made from the
view of the chain (steps added, inserted, moved, linked by an exchange)."""

from arcadia_tool.model.element import ROW_KEY, new_row_key

WAIT = "attesa"  # a row «Attesa: evento atteso» of the path of a chain (between two cycles)
BETWEEN_DOMAINS, WITH_ACTOR = "Tra domini", "Con attore esterno"


def is_wait(row):
    return (row.get("what") or "").strip().lower().startswith(WAIT)


def ident(model, uuid):
    """An element by its ID, else by its label; "" if it does not exist."""
    element = model.get(uuid) if uuid else None
    if element is None:
        return ""
    return element.get("id") or model.label(element)


def domain_of(model, uuid):
    """The domain of a function (of the system function a logical function refines); None for an actor."""
    element, seen = (model.get(uuid) if uuid else None), set()
    while element is not None and element.uuid not in seen:
        seen.add(element.uuid)
        if element.kind == "system_function":
            return model.get(element.get("domain")) if element.get("domain") else None
        if element.kind == "logical_function":
            element = model.get(element.get("refines") or element.get("parent") or "")
            continue
        return None
    return None


# --- the columns of the path computed from the step («#», «Dominio», «Nome funzione») ---------------------------

def step_number(model, rows, index):
    """The position of the step among those that are not waiting rows, from 1 ("" for a waiting row)."""
    if is_wait(rows[index]):
        return ""
    return str(sum(1 for row in rows[:index + 1] if not is_wait(row)))


def step_domain(model, rows, index):
    domain = domain_of(model, rows[index].get("function"))
    return (domain.get("id") or model.label(domain)) if domain is not None else ""


def step_function_name(model, rows, index):
    function = model.get(rows[index].get("function") or "")
    return (function.get("name") or "") if function is not None else ""


STEP_COMPUTED = {"step_number": step_number, "step_domain": step_domain, "function_name": step_function_name}


# --- the fields of the chain computed from its path -----------------------------------------------------------

def involved_domains(model, chain):
    """The domains of the functions of the steps, in the order they appear."""
    found = {}
    for row in chain.get("steps") or []:
        domain = domain_of(model, row.get("function"))
        if domain is not None:
            found.setdefault(domain.uuid, domain)
    return list(found)


def chain_domains(model, chain):
    """«Domini coinvolti»: those of the functions of the steps, in the order they appear, then the others chosen."""
    involved = involved_domains(model, chain)
    return involved + [d for d in dict.fromkeys(chain.get("domains") or []) if d not in involved]


def used_exchanges(model, chain):
    """The exchanges of the steps (the one received, then the one sent), once each, in the order they appear."""
    found = {}
    for row in chain.get("steps") or []:
        for name in ("input", "exchange"):
            fe = model.get(row.get(name) or "")
            if fe is not None and fe.kind == "functional_exchange":
                found.setdefault(fe.uuid, fe)
    return list(found.values())


def exchange_type(model, fe):
    """«Con attore esterno» when an end of the exchange is an external actor, else «Tra domini»."""
    ends = [model.get(fe.get(name) or "") for name in ("source", "target")]
    return WITH_ACTOR if any(e is not None and e.kind == "external_actor" for e in ends) else BETWEEN_DOMAINS


def exchange_nature(model, fe):
    item = model.get(fe.get("exchange_item") or "")
    return (item.get("nature") if item is not None else "") or fe.get("nature") or ""


def used_exchange_rows(model, chain):
    """The rows of «Scambi usati»: each exchange with its producer, user, data, nature, type and state, as texts."""
    return [{"exchange": fe.get("id") or model.label(fe), "source": ident(model, fe.get("source")),
             "target": ident(model, fe.get("target")), "data": ident(model, fe.get("exchange_item")),
             "nature": exchange_nature(model, fe), "type": exchange_type(model, fe), "status": fe.get("status") or ""}
            for fe in used_exchanges(model, chain)]


# --- the fields of the exchange item computed from the exchanges that carry it -----------------------------------

def _ends(model, item, name):
    return list(dict.fromkeys(fe.get(name) for fe in model.of_kind("functional_exchange")
                              if fe.get("exchange_item") == item.uuid and fe.get(name)))


def item_producer(model, item):
    """The producers of the data: the sources of the exchanges that carry it (one only, D10)."""
    return _ends(model, item, "source")


def item_users(model, item):
    """The users of the data: the targets of the exchanges that carry it."""
    return _ends(model, item, "target")


COMPUTED = {"used_exchanges": used_exchange_rows,
            "item_producer": item_producer, "item_users": item_users}


# --- the path composed from the view of the chain ---------------------------------------------------------------

def row_index(rows, key):
    """The position of the row with that key (see Field.row_key), or None."""
    return next((i for i, row in enumerate(rows) if row.get(ROW_KEY) == key), None)


def new_step(function, what, cycle=""):
    row = {ROW_KEY: new_row_key(), "function": function, "what": what}
    if cycle:
        row["cycle"] = cycle
    return row


def new_wait(event):
    """A row «Attesa: …» between two cycles: not a step."""
    text = (event or "").strip()
    return {ROW_KEY: new_row_key(), "what": f"Attesa: {text}" if text else "Attesa"}


def insert_row(rows, row, after=None):
    """The row after the one with the key `after` (at the end without it, or when it is not there)."""
    i = row_index(rows, after) if after else None
    rows.insert(len(rows) if i is None else i + 1, row)
    return row


def move_row(rows, key, delta):
    """The row one place before (-1) or after (+1): True when moved."""
    i = row_index(rows, key)
    j = None if i is None else i + delta
    if j is None or not 0 <= j < len(rows):
        return False
    rows[i], rows[j] = rows[j], rows[i]
    return True


def reverse(rows, first, second):
    """The two steps (their keys) in the opposite order: the second before the first. The exchanges that no longer
    join two steps one after the other leave the path (not the model): the one between them (it went from the first
    to the second), the one of the step before them towards the first, the one of the second towards the step after
    them. Returns the uuids of the exchanges taken out (False if the steps are not there)."""
    i, j = row_index(rows, first), row_index(rows, second)
    if i is None or j is None or i == j:
        return False
    i, j = min(i, j), max(i, j)
    a, b = rows[i], rows[j]
    pairs = [(a, b)]
    before = next((rows[k] for k in range(i - 1, -1, -1) if not is_wait(rows[k])), None)
    after = next((rows[k] for k in range(j + 1, len(rows)) if not is_wait(rows[k])), None)
    if before is not None:
        pairs.append((before, a))
    if after is not None:
        pairs.append((b, after))
    gone = []
    for sender, receiver in pairs:
        sent = sender.get("exchange")
        if sent and receiver.get("input") == sent:
            gone.append(sent)
            for name in ("exchange", "data", "nature"):
                sender.pop(name, None)
            receiver.pop("input", None)
    rows[i], rows[j] = b, a
    return gone


def remove_row(rows, key):
    """The row out of the path; the exchange it sent is no longer the input of the next step."""
    i = row_index(rows, key)
    if i is None:
        return None
    row = rows.pop(i)
    sent = row.get("exchange")
    if sent and i < len(rows) and rows[i].get("input") == sent:
        rows[i].pop("input", None)
    return row


def exchanges_between(model, source, target):
    """The exchanges from an element to another (functions, external actors), by ID."""
    from arcadia_tool.model.element import natural_key
    found = [fe for fe in model.of_kind("functional_exchange")
             if fe.get("source") == source and fe.get("target") == target]
    return sorted(found, key=lambda fe: natural_key(fe.get("id") or ""))


def _carried(model, row, fe):
    """«Dato prodotto» and «Natura» of the step that sends the exchange: its Exchange Item."""
    item = model.get(fe.get("exchange_item") or "")
    row["data"] = (item.get("id") or model.label(item)) if item is not None else (fe.get("name") or "")
    nature = exchange_nature(model, fe)
    if nature:
        row["nature"] = nature


def link(model, rows, source, target, fe):
    """An exchange drawn in the view between two rows (their keys), or from an external actor to a row (source
    None: the trigger, its «Ingresso») or from a row to an actor (target None): «Scambio in uscita» of the first,
    «Ingresso» of the second, «Dato prodotto» and «Natura» from its Exchange Item."""
    fe_element = model.get(fe)
    if source is not None:
        row = rows[row_index(rows, source)]
        row["exchange"] = fe
        if fe_element is not None:
            _carried(model, row, fe_element)
    if target is not None:
        rows[row_index(rows, target)]["input"] = fe


def unlink(rows, source, target):
    """The exchange between two rows out of the path (not out of the model)."""
    first, second = rows[row_index(rows, source)], rows[row_index(rows, target)]
    sent = first.pop("exchange", None)
    for name in ("data", "nature"):
        first.pop(name, None)
    if sent and second.get("input") == sent:
        second.pop("input")
