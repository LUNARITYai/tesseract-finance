import pytest
from pydantic import ValidationError

from tesseract_finance.schemas.pagination import PageParams


def test_page_params_default_to_first_twenty() -> None:
    params = PageParams()

    assert (params.limit, params.offset) == (20, 0)


def test_page_params_accept_the_maximum_limit() -> None:
    params = PageParams.model_validate({"limit": "100", "offset": "40"})

    assert (params.limit, params.offset) == (100, 40)


@pytest.mark.parametrize(
    "raw",
    [{"limit": 101}, {"limit": 0}, {"limit": -1}, {"offset": -1}, {"limit": "abc"}],
)
def test_page_params_reject_out_of_range_values(raw: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        PageParams.model_validate(raw)
