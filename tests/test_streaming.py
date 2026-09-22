import pytest

from streaming_service.main import RangeNotSatisfiable, parse_range


@pytest.mark.parametrize(
    "header, expected",
    [
        (None, None),
        ("bytes=0-99", (0, 99)),
        ("bytes=100-", (100, 999)),
        ("bytes=900-5000", (900, 999)),
        ("bytes=-100", (900, 999)),
        ("bytes=-5000", (0, 999)),
        ("bytes=0-1,5-9", None),
        ("items=0-10", None),
        ("bytes=abc", None),
        ("bytes=50-10", None),
    ],
)
def test_parse_range(header, expected):
    assert parse_range(header, 1000) == expected


@pytest.mark.parametrize("header", ["bytes=1000-", "bytes=5000-6000", "bytes=-0"])
def test_unsatisfiable_range(header):
    with pytest.raises(RangeNotSatisfiable):
        parse_range(header, 1000)
