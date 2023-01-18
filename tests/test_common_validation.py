from enum import Enum
from typing import Any, Type, Union

import pytest
from databento.common.enums import Encoding
from databento.common.validation import validate_enum, validate_maybe_enum


class TestValidation:
    @pytest.mark.parametrize(
        "value, enum",
        [
            [None, Encoding],
        ],
    )
    def test_validate_enum_given_wrong_types_raises_type_error(
        self,
        value: Any,
        enum: Type[Enum],
    ) -> None:
        # Arrange, Act, Assert
        with pytest.raises(TypeError):
            validate_enum(value, enum, "param")

    def test_validate_enum_given_invalid_value_raises_value_error(self) -> None:
        # Arrange, Act, Assert
        with pytest.raises(ValueError):
            validate_enum("invalid", Encoding, "encoding")

    @pytest.mark.parametrize(
        "value, enum, expected",
        [
            ["dbn", Encoding, "dbn"],
            ["DBN", Encoding, "dbn"],
            [Encoding.DBN, Encoding, "dbn"],
        ],
    )
    def test_validate_enum_given_valid_value_returns_expected_output(
        self,
        value: Union[str, Enum],
        enum: Type[Enum],
        expected: Union[str, Enum],
    ) -> None:
        # Arrange, Act, Assert
        assert validate_enum(value, enum, "param") == expected

    def test_validate_maybe_enum_give_none_returns_none(self) -> None:
        # Arrange, Act, Assert
        assert validate_maybe_enum(None, Encoding, "encoding") is None
