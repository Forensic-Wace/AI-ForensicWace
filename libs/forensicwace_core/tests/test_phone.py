from forensicwace_core.utils.phone import format_phone_number, vcard_phone_numbers


def test_format_with_prefix():
    assert format_phone_number("+39 333 123 4567") == "+39 333 123 4567"


def test_format_without_prefix():
    assert format_phone_number("3331234567") == "333 123 4567"


def test_invalid_number_returns_none():
    assert format_phone_number("not a number") is None


def test_vcard_extraction():
    vcard = "BEGIN:VCARD\nTEL;TYPE=CELL:+39 333 1234567\nEND:VCARD"
    assert vcard_phone_numbers(vcard) == ["+39 333 1234567"]
