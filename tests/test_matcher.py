import pytest
import regex

from matcher import (
    CustomTrigger,
    RegexValidationError,
    compile_custom,
    compile_stored,
    match_message,
)

BUILTINS = {"meow": True, "woof": False}


def make_custom(name, pattern, enabled=True):
    return CustomTrigger(
        name=name,
        name_lower=name.lower(),
        pattern=pattern,
        compiled=regex.compile(pattern, regex.IGNORECASE),
        enabled=enabled,
    )


@pytest.mark.parametrize(
    "content",
    [
        "meow",
        "mreow",
        "mew",
        "mrow",
        "mrrp",
        "nya",
        "purr",
        "MEOW",
        "meow!!",
        "meow :3",
        "**meow**",
        "meow meow",
    ],
)
def test_meow_builtin_matches(content):
    result = match_message(content, [], BUILTINS)
    assert result is not None
    assert result.pool == "meow"
    assert result.is_builtin is True


@pytest.mark.parametrize(
    "content",
    ["hello", "woof", "the meow is loud", "meowing", "hello mrrp"],
)
def test_non_matches(content):
    assert match_message(content, [], BUILTINS) is None


def test_woof_disabled_by_default():
    assert match_message("woof", [], {"meow": True, "woof": False}) is None


def test_woof_when_enabled():
    result = match_message("woof", [], {"meow": True, "woof": True})
    assert result is not None
    assert result.pool == "woof"


def test_custom_checked_first():
    trigger = make_custom("mrrp", r"^mrrp$")
    result = match_message("mrrp", [trigger], BUILTINS)
    assert result is not None
    assert result.trigger_name == "mrrp"
    assert result.is_builtin is False


def test_disabled_custom_ignored():
    trigger = make_custom("mrrp", r"^mrrp$", enabled=False)
    result = match_message("mrrp", [trigger], BUILTINS)
    assert result is not None
    assert result.is_builtin is True


def test_custom_no_match_falls_through():
    trigger = make_custom("hello", r"^hello$")
    result = match_message("meow", [trigger], BUILTINS)
    assert result is not None
    assert result.is_builtin is True


@pytest.mark.parametrize("content", ["", "   ", "\n\t"])
def test_empty_content(content):
    assert match_message(content, [], BUILTINS) is None


def test_compile_custom_accepts_safe_pattern():
    compiled = compile_custom(r"^mrr+p+$")
    assert compiled.search("mrrp")


@pytest.mark.parametrize("pattern", ["", "   ", "("])
def test_compile_custom_rejects_invalid(pattern):
    with pytest.raises(RegexValidationError):
        compile_custom(pattern)


def test_compile_custom_rejects_too_long():
    with pytest.raises(RegexValidationError):
        compile_custom("a" * 201)


def test_compile_custom_rejects_empty_match():
    with pytest.raises(RegexValidationError):
        compile_custom(r"^$")


def test_compile_stored_accepts_safe_pattern():
    compiled = compile_stored(r"^mrr+p+$")
    assert compiled is not None
    assert compiled.search("mrrp")


@pytest.mark.parametrize("pattern", ["", "(", r"^$", "a" * 201])
def test_compile_stored_rejects_bad(pattern):
    assert compile_stored(pattern) is None
