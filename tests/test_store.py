import pytest

from matcher import MAX_CUSTOM_TRIGGERS, RegexValidationError

GUILD = 123456789
REPLY = "mrrp back :3"


def test_defaults(store):
    config = store.get(GUILD)
    assert config.enabled is True
    assert config.builtin_enabled == {"meow": True, "woof": False}
    assert config.custom_triggers == []


def test_set_enabled(store):
    store.set_enabled(GUILD, False)
    assert store.get(GUILD).enabled is False
    store.set_enabled(GUILD, True)
    assert store.get(GUILD).enabled is True


def test_toggle_builtin(store):
    store.set_trigger_enabled(GUILD, "builtin", "woof", True)
    assert store.get(GUILD).builtin_enabled["woof"] is True
    store.set_trigger_enabled(GUILD, "builtin", "woof", False)
    assert store.get(GUILD).builtin_enabled["woof"] is False


def test_toggle_unknown_kind(store):
    with pytest.raises(ValueError):
        store.set_trigger_enabled(GUILD, "other", "x", True)


def test_add_custom(store):
    name = store.add_custom(
        GUILD, "mrrp", r"^mrr+p+$", REPLY, created_by=42
    )
    assert name == "mrrp"
    config = store.get(GUILD)
    assert len(config.custom_triggers) == 1
    trigger = config.custom_triggers[0]
    assert trigger.name == "mrrp"
    assert trigger.name_lower == "mrrp"
    assert trigger.enabled is True
    assert trigger.response == REPLY
    assert trigger.simple_text is None
    assert trigger.compiled.search("mrrp")


def test_add_custom_stores_simple_text(store):
    store.add_custom(
        GUILD, "good morning", r"good morning", REPLY, simple_text="good morning"
    )
    trigger = store.get(GUILD).custom_triggers[0]
    assert trigger.simple_text == "good morning"


def test_add_custom_requires_response(store):
    with pytest.raises(RegexValidationError):
        store.add_custom(GUILD, "mrrp", r"^mrrp$", "   ")


def test_add_custom_duplicate(store):
    store.add_custom(GUILD, "mrrp", r"^mrrp$", REPLY)
    with pytest.raises(RegexValidationError):
        store.add_custom(GUILD, "MRRP", r"^mrrp$", REPLY)


def test_add_custom_invalid(store):
    with pytest.raises(RegexValidationError):
        store.add_custom(GUILD, "bad", "(", REPLY)


def test_add_custom_empty_name(store):
    with pytest.raises(RegexValidationError):
        store.add_custom(GUILD, "   ", r"^mrrp$", REPLY)


def test_add_custom_name_too_long(store):
    with pytest.raises(RegexValidationError):
        store.add_custom(GUILD, "a" * 33, r"^mrrp$", REPLY)


def test_update_custom(store):
    store.add_custom(GUILD, "mrrp", r"^mrrp$", REPLY)
    name = store.update_custom(
        GUILD, "mrrp", "mrrp", r"^mrr+p+$", "new reply", simple_text="mrrp"
    )
    assert name == "mrrp"
    trigger = store.get_custom(GUILD, "mrrp")
    assert trigger.pattern == r"^mrr+p+$"
    assert trigger.response == "new reply"
    assert trigger.simple_text == "mrrp"


def test_update_custom_changes_name(store):
    store.add_custom(GUILD, "mrrp", r"^mrrp$", REPLY)
    store.update_custom(GUILD, "mrrp", "purr", r"^purr$", REPLY)
    assert store.get_custom(GUILD, "mrrp") is None
    assert store.get_custom(GUILD, "purr") is not None


def test_update_custom_duplicate(store):
    store.add_custom(GUILD, "mrrp", r"^mrrp$", REPLY)
    store.add_custom(GUILD, "purr", r"^purr$", REPLY)
    with pytest.raises(RegexValidationError):
        store.update_custom(GUILD, "mrrp", "purr", r"^mrrp$", REPLY)


def test_update_custom_missing(store):
    with pytest.raises(RegexValidationError):
        store.update_custom(GUILD, "mrrp", "mrrp", r"^mrrp$", REPLY)


def test_remove_custom(store):
    store.add_custom(GUILD, "mrrp", r"^mrrp$", REPLY)
    store.remove_custom(GUILD, "mrrp")
    assert store.custom_trigger_names(GUILD) == []


def test_toggle_custom(store):
    store.add_custom(GUILD, "mrrp", r"^mrrp$", REPLY)
    store.set_trigger_enabled(GUILD, "custom", "mrrp", False)
    assert store.get(GUILD).custom_triggers[0].enabled is False


def test_list_triggers(store):
    store.add_custom(GUILD, "mrrp", r"^mrrp$", REPLY)
    items = store.list_triggers(GUILD)
    kinds = {(item["kind"], item["key"]) for item in items}
    assert ("builtin", "meow") in kinds
    assert ("builtin", "woof") in kinds
    assert ("custom", "mrrp") in kinds
    custom_item = next(item for item in items if item["kind"] == "custom")
    assert custom_item["label"] == "mrrp"
    assert custom_item["custom"] is True
    assert custom_item["response"] == REPLY


def test_max_custom_triggers(store):
    for index in range(MAX_CUSTOM_TRIGGERS):
        store.add_custom(GUILD, f"trig{index}", rf"^mrrp{index}$", REPLY)
    with pytest.raises(RegexValidationError):
        store.add_custom(GUILD, "one-more", r"^mrrp-extra$", REPLY)
