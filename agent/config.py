"""Constants and configuration for the agent extension."""

from pathlib import Path

# Directories
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
CONFIG_DIR = PROJECT_ROOT / "config"
CHATS_DIR = PROJECT_ROOT / "data" / "agent" / "chats"
OUTPUTS_DIR = PROJECT_ROOT / "data" / "agent" / "outputs"

# Agent settings
DEFAULT_MODEL = "gpt-4o"
MAX_TOOL_ITERATIONS = 15

# Model presets available in the UI
MODEL_PRESETS = {
    "gpt-4o": "gpt-4o",
    "gpt-4o-mini": "gpt-4o-mini",
    "claude-sonnet": "anthropic/claude-sonnet-4-20250514",
    "claude-haiku": "anthropic/claude-haiku-4-5-20251001",
}

# Semantic categories for field classification
SEMANTIC_CATEGORIES = {
    "political": [
        "government_type", "legislature", "upper_house", "lower_house",
        "leader_title1", "leader_name1", "leader_title2", "leader_name2",
        "leader_title3", "leader_name3", "leader_title4", "leader_name4",
        "leader_title5", "leader_name5", "leaders",
    ],
    "economic": [
        "GDP_PPP", "GDP_PPP_year", "GDP_PPP_per_capita", "GDP_PPP_rank",
        "GDP_nominal", "GDP_nominal_year", "GDP_nominal_per_capita",
        "GDP_nominal_rank", "currency", "currency_code",
        "Gini", "Gini_year", "Gini_change",
    ],
    "demographic": [
        "population_estimate", "population_estimate_year",
        "population_census", "population_census_year",
        "population_density_km2", "demonym",
        "ethnic_groups", "ethnic_groups_year",
        "religion", "religion_year",
    ],
    "geographic": [
        "area_km2", "area_rank", "percent_water",
        "capital", "largest_city", "coordinates",
        "time_zone", "utc_offset", "drives_on",
    ],
    "cultural": [
        "official_languages", "languages", "languages_type",
        "languages2", "languages2_type",
        "native_name", "national_motto", "national_anthem",
    ],
    "development": [
        "HDI", "HDI_year", "HDI_change", "HDI_rank",
    ],
    "international": [
        "calling_code", "cctld", "iso3166code",
    ],
    "historical": [
        "established", "established_event1", "established_date1",
        "established_event2", "established_date2",
        "established_event3", "established_date3",
        "established_event4", "established_date4",
        "established_event5", "established_date5",
    ],
}
