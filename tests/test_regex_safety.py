import pytest
import regex

from matcher import (
    CustomTrigger,
    RegexValidationError,
    compile_custom,
    compile_stored,
    match_message,
)


@pytest.mark.parametrize(
    "pattern",
    [
        r"(a+)+$",
        r"(a|aa)+$",
        r"(a+)+c",
        r"(a*)*$",
        r"(a|a?)+$",
    ],
)
def test_catastrophic_patterns_rejected(pattern):
    with pytest.raises(RegexValidationError):
        compile_custom(pattern)


@pytest.mark.parametrize(
    "pattern",
    [
        r"^mrr+p+$",
        r"^(meow|mreow)$",
        r"^nya+$",
        r"^purr+$",
        r"^(meow )+$",
    ],
)
def test_safe_patterns_accepted(pattern):
    assert compile_custom(pattern) is not None


def test_stored_catastrophic_rejected():
    assert compile_stored(r"(a+)+$") is None


def test_runtime_timeout_is_caught():
    compiled = regex.compile(r"(a+)+$", regex.IGNORECASE)
    trigger = CustomTrigger(
        name="slow",
        name_lower="slow",
        pattern=r"(a+)+$",
        compiled=compiled,
        enabled=True,
    )
    result = match_message(
        "a" * 30000 + "!", [trigger], {"meow": False, "woof": False}
    )
    assert result is None


def test_pattern_length_limit():
    with pytest.raises(RegexValidationError):
        compile_custom("a" * 201)
    assert compile_stored("a" * 201) is None
