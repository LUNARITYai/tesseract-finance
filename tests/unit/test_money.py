from decimal import Decimal

import pytest
from pydantic import BaseModel

from tesseract_finance.schemas.money import Amount, parse_amount


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("25.00", Decimal("25.00")),
        ("25", Decimal("25.00")),
        ("25.5", Decimal("25.50")),
        ("0.01", Decimal("0.01")),
        ("25.100", Decimal("25.10")),
        ("9999999999.99", Decimal("9999999999.99")),
        (25, Decimal("25.00")),
        (25.1, Decimal("25.10")),
        (0.07, Decimal("0.07")),
        (Decimal("3.5"), Decimal("3.50")),
    ],
)
def test_parse_amount_accepts_positive_two_place_values(raw: object, expected: Decimal) -> None:
    parsed = parse_amount(raw)

    assert parsed == expected
    assert parsed.as_tuple().exponent == -2


@pytest.mark.parametrize(
    "raw",
    [
        "0",
        "0.00",
        0,
        "-1.00",
        -5,
        "0.001",
        "25.123",
        25.123,
        "10000000000.00",
        10_000_000_000,
        "abc",
        "",
        "25,00",
        "NaN",
        "Infinity",
        float("inf"),
        True,
        None,
        [],
    ],
)
def test_parse_amount_rejects_invalid_values(raw: object) -> None:
    with pytest.raises(ValueError):
        parse_amount(raw)


class _Priced(BaseModel):
    amount: Amount


def test_amount_serializes_as_two_place_string() -> None:
    assert _Priced(amount=7).model_dump(mode="json") == {"amount": "7.00"}
    assert _Priced.model_validate_json('{"amount": 12.5}').amount == Decimal("12.50")
