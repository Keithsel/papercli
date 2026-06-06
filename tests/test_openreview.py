from papercli.crawlers.openreview import _value


def test_value_unwraps_api2_shape():
    assert _value({"title": {"value": "Hello"}}, "title") == "Hello"


def test_value_passes_through_plain():
    assert _value({"title": "Hello"}, "title") == "Hello"


def test_value_missing_key_returns_none():
    assert _value({}, "title") is None
