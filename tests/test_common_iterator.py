from collections.abc import Iterable

import pytest
from databento.common import iterator


@pytest.mark.parametrize(
    "things, size, expected",
    [
        (
            "abcdefg",
            2,
            [
                ("a", "b"),
                ("c", "d"),
                ("e", "f"),
                ("g",),
            ],
        ),
    ],
)
def test_chunk(
    things: Iterable[object],
    size: int,
    expected: Iterable[tuple[object]],
) -> None:
    """
    Test that an iterable is chunked property.
    """
    # Arrange, Act, Assert
    chunks = [chunk for chunk in iterator.chunk(things, size)]
    assert chunks == expected
