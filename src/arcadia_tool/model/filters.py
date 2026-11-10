"""Conditions on the columns of a list, joined in sequence with «E» (and) and «O» (or), with brackets for mixed
expressions: «E» binds before «O», as usual (A E B O C is (A E B) O C). Used by the catalogue of the ADR."""
from dataclasses import dataclass

AND, OR = "E", "O"
CONTAINS, NOT_CONTAINS, EQUALS, NOT_EQUALS, EMPTY, NOT_EMPTY = (
    "contiene", "non contiene", "è uguale a", "è diverso da", "è vuoto", "non è vuoto")
OPERATORS = (CONTAINS, NOT_CONTAINS, EQUALS, NOT_EQUALS, EMPTY, NOT_EMPTY)
WITHOUT_VALUE = (EMPTY, NOT_EMPTY)


class FilterError(ValueError):
    """An expression that cannot be read (brackets not balanced)."""


@dataclass
class Condition:
    column: str
    operator: str = CONTAINS
    value: str = ""
    join: str = AND  # with the condition before it (not used by the first one)
    opens: int = 0  # brackets opened before it
    closes: int = 0  # brackets closed after it


def parts(text):
    """The values of a cell: its text, and each of the values of a list («DF01, DF02»)."""
    text = (text or "").strip()
    return [text, *[p.strip() for p in text.split(",") if p.strip()]] if "," in text else [text]


def holds(condition, text):
    """The condition on the text of a cell (not case sensitive; «è uguale a» also on one of the values of a list)."""
    text = (text or "").strip().lower()
    value = (condition.value or "").strip().lower()
    op = condition.operator
    if op == EMPTY:
        return not text
    if op == NOT_EMPTY:
        return bool(text)
    if op == CONTAINS:
        return value in text
    if op == NOT_CONTAINS:
        return value not in text
    equal = any(p.lower() == value for p in parts(text))
    return equal if op == EQUALS else not equal


def check(conditions):
    """Why the expression cannot be read, or None."""
    depth = 0
    for c in conditions:
        depth += c.opens
        depth -= c.closes
        if depth < 0:
            return "Una parentesi è chiusa prima di essere aperta."
    return "Parentesi non bilanciate: aperte e chiuse non sono lo stesso numero." if depth else None


def evaluate(conditions, cell):
    """The expression on a row: cell(column) → its text. True without conditions. Raises FilterError if it cannot
    be read."""
    if not conditions:
        return True
    problem = check(conditions)
    if problem:
        raise FilterError(problem)
    tokens = []  # "(", ")", AND, OR, or a bool
    for i, c in enumerate(conditions):
        if i:
            tokens.append(c.join if c.join in (AND, OR) else AND)
        tokens += ["("] * c.opens + [holds(c, cell(c.column))] + [")"] * c.closes
    position = 0

    def expression():  # terms joined by O
        nonlocal position
        value = term()
        while position < len(tokens) and tokens[position] == OR:
            position += 1
            right = term()
            value = value or right
        return value

    def term():  # factors joined by E
        nonlocal position
        value = factor()
        while position < len(tokens) and tokens[position] == AND:
            position += 1
            right = factor()
            value = value and right
        return value

    def factor():
        nonlocal position
        token = tokens[position]
        position += 1
        if token == "(":
            value = expression()
            position += 1  # its ")"
            return value
        return token
    return expression()
