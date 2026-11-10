import logging
import random
from dataclasses import dataclass

import regex

logger = logging.getLogger("matcher")

MAX_PATTERN_LENGTH = 200
MAX_CUSTOM_TRIGGERS = 25
MAX_NAME_LENGTH = 32
MAX_RESPONSE_LENGTH = 500
MAX_SIMPLE_LENGTH = 32
MATCH_TIMEOUT = 0.05
VALIDATION_TIMEOUT = 0.1

CAT_PATTERN = r"^\**((m+[erao]+[wp]+|n+y+a+|p+u*r+)s*\**\s*)+~*\s*[.!?]*\s*(:3+)?\**$"
DOG_PATTERN = r"^\**((w+[oa]+f+|b+a+r+k+|a+r+f+|w*r+u+f+|a+w+o+)s*\**\s*)+~*\s*[.!?]*\s*(:3+)?\**$"


@dataclass(frozen=True)
class BuiltinTrigger:
    key: str
    label: str
    pattern: str
    pool: str
    default_enabled: bool


BUILTIN_TRIGGERS = (
    BuiltinTrigger("meow", "meow", CAT_PATTERN, "meow", True),
    BuiltinTrigger("woof", "woof", DOG_PATTERN, "woof", False),
)

COMPILED_BUILTINS = {
    trigger.key: regex.compile(trigger.pattern, regex.IGNORECASE)
    for trigger in BUILTIN_TRIGGERS
}


class RegexValidationError(ValueError):
    pass


def _corpus():
    rng = random.Random(0)
    alphabet = "meownya!?~*:3 "
    noise = "".join(rng.choice(alphabet) for _ in range(20000))
    return (
        "a" * 20000,
        "a" * 20000 + "!",
        "a" * 20000 + "b",
        "m" * 20000,
        "meow " * 4000,
        "!" * 20000,
        "(" * 5000,
        "mrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrp" * 1000,
        noise,
    )


VALIDATION_CORPUS = _corpus()


def compile_custom(pattern):
    pattern = (pattern or "").strip()
    if not pattern:
        raise RegexValidationError("Give the trigger a regex.")
    if len(pattern) > MAX_PATTERN_LENGTH:
        raise RegexValidationError(
            f"That regex is too long. Keep it under {MAX_PATTERN_LENGTH} characters."
        )

    try:
        compiled = regex.compile(pattern, regex.IGNORECASE)
    except regex.error as exc:
        raise RegexValidationError(f"That regex is not valid: {exc}") from exc

    try:
        if compiled.search("", timeout=VALIDATION_TIMEOUT):
            raise RegexValidationError(
                "That regex matches an empty message. Make it more specific."
            )
    except TimeoutError as exc:
        raise RegexValidationError("That regex is too slow. Simplify it.") from exc

    for sample in VALIDATION_CORPUS:
        try:
            compiled.search(sample, timeout=VALIDATION_TIMEOUT)
        except TimeoutError as exc:
            raise RegexValidationError("That regex is too slow. Simplify it.") from exc
        except regex.error as exc:
            raise RegexValidationError(f"That regex failed a safety test: {exc}") from exc

    return compiled


def build_simple_pattern(text):
    text = (text or "").strip()
    if not text:
        raise RegexValidationError("Give the trigger something to match.")
    if len(text) > MAX_SIMPLE_LENGTH:
        raise RegexValidationError(
            f"That trigger is too long. Keep it under {MAX_SIMPLE_LENGTH} characters."
        )

    escaped = regex.escape(text)
    prefix = r"(?<!\w)" if text[0].isalnum() or text[0] == "_" else ""
    suffix = r"(?!\w)" if text[-1].isalnum() or text[-1] == "_" else ""
    pattern = f"{prefix}{escaped}{suffix}"
    compile_custom(pattern)
    return pattern


def compile_stored(pattern):
    pattern = (pattern or "").strip()
    if not pattern or len(pattern) > MAX_PATTERN_LENGTH:
        return None

    try:
        compiled = regex.compile(pattern, regex.IGNORECASE)
    except regex.error:
        return None

    try:
        if compiled.search("", timeout=MATCH_TIMEOUT):
            return None
        for sample in VALIDATION_CORPUS:
            compiled.search(sample, timeout=MATCH_TIMEOUT)
    except (TimeoutError, regex.error):
        return None

    return compiled


@dataclass
class CustomTrigger:
    name: str
    name_lower: str
    pattern: str
    compiled: object
    enabled: bool = True
    response: str = ""
    simple_text: str | None = None


@dataclass
class MatchResult:
    pool: str
    trigger_name: str
    is_builtin: bool
    response: str | None = None


def match_message(content, custom_triggers, builtin_enabled):
    content = content.strip()
    if not content:
        return None

    for trigger in custom_triggers:
        if not trigger.enabled:
            continue
        try:
            if trigger.compiled.search(content, timeout=MATCH_TIMEOUT):
                return MatchResult(
                    pool="meow",
                    trigger_name=trigger.name,
                    is_builtin=False,
                    response=trigger.response or None,
                )
        except TimeoutError:
            logger.warning("Regex timeout for custom trigger %r", trigger.name)
        except regex.error:
            logger.warning("Regex error for custom trigger %r", trigger.name, exc_info=True)

    for trigger in BUILTIN_TRIGGERS:
        if not builtin_enabled.get(trigger.key, trigger.default_enabled):
            continue
        compiled = COMPILED_BUILTINS[trigger.key]
        try:
            if compiled.search(content, timeout=MATCH_TIMEOUT):
                return MatchResult(pool=trigger.pool, trigger_name=trigger.label, is_builtin=True)
        except TimeoutError:
            logger.warning("Regex timeout for built in trigger %r", trigger.key)

    return None
