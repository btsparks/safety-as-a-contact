"""Tests for backend.coaching.trades — trade data + fuzzy matching."""

from backend.coaching.trades import (
    DEFAULT_TRADE_PROFILE,
    TRADE_PROFILES,
    get_trade_profile,
)


def test_all_12_trades_defined():
    """Should have exactly 12 trade profiles."""
    assert len(TRADE_PROFILES) == 12


def test_each_trade_has_required_fields():
    """Every trade profile must have all required keys."""
    required_keys = {"label", "hazard_profile", "coaching_focus", "common_equipment", "osha_focus", "experience_calibration"}
    for key, profile in TRADE_PROFILES.items():
        assert required_keys.issubset(profile.keys()), f"Trade '{key}' missing keys"
        # Experience calibration must have 3 levels
        assert set(profile["experience_calibration"].keys()) == {"entry", "intermediate", "expert"}, f"Trade '{key}' missing experience levels"


def test_direct_match():
    """Direct trade key should return correct profile."""
    profile = get_trade_profile("ironworker")
    assert profile["label"] == "Ironworker"

    profile = get_trade_profile("electrician")
    assert profile["label"] == "Electrician"


def test_case_insensitive():
    """Trade matching should be case-insensitive."""
    profile = get_trade_profile("IRONWORKER")
    assert profile["label"] == "Ironworker"

    profile = get_trade_profile("Carpenter")
    assert profile["label"] == "Carpenter"


def test_alias_matching():
    """Aliases should resolve to correct trade."""
    assert get_trade_profile("operator")["label"] == "Operating Engineer"
    assert get_trade_profile("concrete")["label"] == "Cement Mason"
    assert get_trade_profile("pipe fitter")["label"] == "Plumber"
    assert get_trade_profile("sparky")["label"] == "Electrician"
    assert get_trade_profile("tin knocker")["label"] == "Sheet Metal Worker"
    assert get_trade_profile("scaffolder")["label"] == "Scaffold Builder"


def test_fuzzy_matching():
    """Close misspellings should still match."""
    profile = get_trade_profile("ironwrker")  # missing 'o'
    assert profile["label"] == "Ironworker"

    profile = get_trade_profile("electrcian")  # transposed
    assert profile["label"] == "Electrician"


def test_none_returns_default():
    """None trade should return default profile."""
    profile = get_trade_profile(None)
    assert profile == DEFAULT_TRADE_PROFILE


def test_empty_string_returns_default():
    """Empty string should return default profile."""
    profile = get_trade_profile("")
    assert profile == DEFAULT_TRADE_PROFILE


def test_unknown_trade_returns_default():
    """Completely unknown trade should return default profile."""
    profile = get_trade_profile("astronaut")
    assert profile == DEFAULT_TRADE_PROFILE
    assert profile["label"] == "General Construction"


def test_default_trade_has_required_fields():
    """Default profile must have same structure as trade profiles."""
    required_keys = {"label", "hazard_profile", "coaching_focus", "common_equipment", "osha_focus", "experience_calibration"}
    assert required_keys.issubset(DEFAULT_TRADE_PROFILE.keys())


def test_hyphen_and_underscore_normalization():
    """Hyphens and underscores should be interchangeable."""
    profile = get_trade_profile("operating-engineer")
    assert profile["label"] == "Operating Engineer"

    profile = get_trade_profile("sheet_metal")
    assert profile["label"] == "Sheet Metal Worker"
