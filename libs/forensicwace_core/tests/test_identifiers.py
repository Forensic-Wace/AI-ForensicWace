import pytest

from forensicwace_core.backups.ios import validate_identifier
from forensicwace_core.exceptions import InvalidIdentifierError


@pytest.mark.parametrize("bad", ["..", "../x", "a/b", "a\\b", "", "."])
def test_traversal_identifiers_are_rejected(bad):
    with pytest.raises(InvalidIdentifierError):
        validate_identifier(bad)


def test_plain_identifiers_pass():
    assert validate_identifier("00008030-000A1B2C3D4E5F6G") == "00008030-000A1B2C3D4E5F6G"
