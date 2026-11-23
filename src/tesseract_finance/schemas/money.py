from decimal import Decimal, InvalidOperation
from typing import Annotated

from pydantic import BeforeValidator, PlainSerializer

CENT = Decimal("0.01")
NUMERIC_12_2_MAX = Decimal("9999999999.99")


def parse_amount(value: object) -> Decimal:
    """Turn a JSON string or number into a positive Decimal with exactly two places.

    Floats go through ``str`` so ``25.1`` becomes ``Decimal("25.1")`` (the shortest
    representation, matching the JSON text), not the binary float's long expansion.
    """
    if isinstance(value, bool) or not isinstance(value, str | int | float | Decimal):
        raise ValueError("amount must be a decimal string or number")
    try:
        amount = Decimal(str(value)) if isinstance(value, float) else Decimal(value)
    except InvalidOperation:
        raise ValueError("amount must be a decimal number") from None
    if not amount.is_finite():
        raise ValueError("amount must be a finite number")
    if amount <= 0:
        raise ValueError("amount must be greater than 0")
    if amount > NUMERIC_12_2_MAX:
        raise ValueError(f"amount must be at most {NUMERIC_12_2_MAX}")
    quantized = amount.quantize(CENT)
    if quantized != amount:
        raise ValueError("amount must have at most 2 decimal places")
    return quantized


def format_amount(amount: Decimal) -> str:
    return f"{amount:.2f}"


Amount = Annotated[
    Decimal,
    BeforeValidator(parse_amount),
    PlainSerializer(format_amount, return_type=str, when_used="json"),
]
