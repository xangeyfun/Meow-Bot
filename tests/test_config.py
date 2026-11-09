from cogs.config import _format_labels


def test_format_labels_empty():
    assert _format_labels([]) == "nothing"


def test_format_labels_short():
    assert _format_labels(["meow", "woof"]) == "meow, woof"


def test_format_labels_truncates():
    labels = ["x" * 32 + " (custom)" for _ in range(25)] + ["meow", "woof"]
    value = _format_labels(labels)
    assert len(value) <= 1024
    assert "more" in value
