import re

from luml.utils.naming import ADJECTIVES, NOUNS, generate_random_name

NAME_PATTERN = re.compile(r"^[a-z]+-[a-z]+-\d{3}$")


def test_format_matches_pattern() -> None:
    for _ in range(50):
        name = generate_random_name()
        assert NAME_PATTERN.match(name), (
            f"Name '{name}' does not match expected pattern"
        )


def test_adjectives_minimum_count() -> None:
    assert len(ADJECTIVES) >= 150


def test_nouns_minimum_count() -> None:
    assert len(NOUNS) >= 150


def test_adjectives_are_lowercase_ascii_no_hyphens() -> None:
    for word in ADJECTIVES:
        assert word == word.lower(), f"Adjective '{word}' is not lowercase"
        assert word.isascii(), f"Adjective '{word}' contains non-ASCII characters"
        assert "-" not in word, f"Adjective '{word}' contains a hyphen"


def test_nouns_are_lowercase_ascii_no_hyphens() -> None:
    for word in NOUNS:
        assert word == word.lower(), f"Noun '{word}' is not lowercase"
        assert word.isascii(), f"Noun '{word}' contains non-ASCII characters"
        assert "-" not in word, f"Noun '{word}' contains a hyphen"


def test_multiple_calls_produce_varying_results() -> None:
    names = {generate_random_name() for _ in range(20)}
    assert len(names) > 1, "Expected varying names across multiple calls"


def test_name_parts_come_from_dictionaries() -> None:
    for _ in range(50):
        name = generate_random_name()
        adjective, noun, number = name.rsplit("-", 2)
        assert adjective in ADJECTIVES, f"Adjective '{adjective}' not in ADJECTIVES"
        assert noun in NOUNS, f"Noun '{noun}' not in NOUNS"
        assert 0 <= int(number) <= 999


def test_number_is_zero_padded() -> None:
    found_leading_zero = False
    for _ in range(500):
        name = generate_random_name()
        number_str = name.rsplit("-", 1)[1]
        assert len(number_str) == 3
        if number_str[0] == "0":
            found_leading_zero = True
    assert found_leading_zero, "Expected at least one zero-padded number in 500 calls"
