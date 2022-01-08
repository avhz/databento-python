import pytest
from databento.common.enums import Compression, Encoding
from databento.common.validation import validate_enum


class TestValidation:
    @pytest.mark.parametrize(
        "value, enum, param",
        [
            [None, Encoding, "encoding"],
            [Compression.ZSTD, Encoding, "encoding"],
        ],
    )
    def test_validate_enum_given_wrong_types_raises_type_error(
        self,
        value,
        enum,
        param,
    ) -> None:
        # Arrange, Act, Assert
        with pytest.raises(TypeError):
            validate_enum(value, enum, "param")

    def test_validate_enum_given_invalid_value_raises_value_error(self) -> None:
        # Arrange, Act, Assert
        with pytest.raises(ValueError):
            validate_enum("invalid", Encoding, "encoding")

    @pytest.mark.parametrize(
        "value, enum, param, expected",
        [
            ["bin", Encoding, "encoding", "bin"],
            ["BIN", Encoding, "encoding", "bin"],
            [Encoding.BIN, Encoding, "encoding", Encoding.BIN],
        ],
    )
    def test_validate_enum_given_valid_value_returns_expected_output(
        self,
        value,
        enum,
        param,
        expected,
    ) -> None:
        # Arrange, Act, Assert
        assert validate_enum(value, enum, "param") == expected
