"""
Fetch Wikipedia country infoboxes using wptools and save them as XML.

Usage:
    from src.collection.scraper import scrape_country, scrape_all_countries
"""

import json
import time
import logging
from pathlib import Path

import wptools

from src.collection.wikitext_cleaner import clean_value
from src.collection.xml_formatter import build_xml, write_xml

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

RAW_DIR = Path('data/raw')
CONFIG_DIR = Path('config')

INFOBOX_TEMPLATES = {'infobox country', 'infobox sovereign state'}

# Delay between Wikipedia API requests (seconds) to be polite
REQUEST_DELAY = 1.0


# ---------------------------------------------------------------------------
# Field alias normalisation
# ---------------------------------------------------------------------------

def _load_aliases() -> dict[str, str]:
    path = CONFIG_DIR / 'field_aliases.json'
    if path.exists():
        return json.loads(path.read_text(encoding='utf-8'))
    return {}


def _apply_aliases(data: dict, aliases: dict[str, str]) -> dict:
    """
    Rename variant field names to their canonical forms.
    aliases maps  variant → canonical.
    If both variant and canonical exist, canonical takes precedence.
    """
    result = {}
    for key, value in data.items():
        canonical = aliases.get(key, key)
        if canonical not in result:
            result[canonical] = value
        # else: canonical already present, skip variant
    return result


# ---------------------------------------------------------------------------
# Tokenization config
# ---------------------------------------------------------------------------

def _load_tokenization_strategy() -> str:
    path = CONFIG_DIR / 'tokenization.json'
    if path.exists():
        cfg = json.loads(path.read_text(encoding='utf-8'))
        return cfg.get('strategy', 'single_node')
    return 'single_node'


# ---------------------------------------------------------------------------
# Core scraping logic
# ---------------------------------------------------------------------------

def _fetch_infobox(country_name: str) -> dict | None:
    """
    Fetch the infobox template data for a Wikipedia page.
    Returns a flat dict of field→value, or None on failure.
    """
    try:
        page = wptools.page(country_name, silent=True)
        page.get_parse()
    except Exception as e:
        log.error(f"Failed to fetch '{country_name}': {e}")
        return None

    templates = page.data.get('infobox') or {}
    if not templates:
        log.warning(f"No infobox found for '{country_name}'")
        return None

    # wptools returns a list of dicts or a single dict depending on version
    if isinstance(templates, list):
        # Find the first matching infobox template
        for t in templates:
            tname = t.get('template', '').lower()
            if any(tname.startswith(ib) for ib in INFOBOX_TEMPLATES):
                return {k: v for k, v in t.items() if k != 'template'}
        log.warning(f"No 'Infobox country' template found for '{country_name}'. Templates: {[t.get('template') for t in templates]}")
        return None
    elif isinstance(templates, dict):
        return {k: v for k, v in templates.items() if k != 'template'}
    else:
        log.warning(f"Unexpected infobox type for '{country_name}': {type(templates)}")
        return None


def scrape_country(country_name: str, output_dir: Path | None = None) -> Path | None:
    """
    Scrape a single country's infobox and write it to XML.

    :param country_name: Wikipedia page title (e.g. 'Lebanon')
    :param output_dir: destination directory (defaults to data/raw/)
    :return: Path to the written XML file, or None on failure
    """
    out_dir = output_dir or RAW_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / f"{country_name.replace(' ', '_')}.xml"
    if out_path.exists():
        log.info(f"Skipping '{country_name}' — already exists at {out_path}")
        return out_path

    log.info(f"Fetching '{country_name}' …")
    raw = _fetch_infobox(country_name)
    if raw is None:
        return None

    aliases = _load_aliases()
    normalised = _apply_aliases(raw, aliases)

    strategy = _load_tokenization_strategy()
    element = build_xml(country_name, normalised, tokenization_strategy=strategy)
    write_xml(element, out_path)
    log.info(f"Wrote {out_path}")
    return out_path


def scrape_all_countries(
    countries: list[str],
    output_dir: Path | None = None,
    delay: float = REQUEST_DELAY,
) -> dict[str, Path | None]:
    """
    Scrape all countries in the list.

    :param countries: list of Wikipedia page titles
    :param output_dir: destination directory (defaults to data/raw/)
    :param delay: seconds to wait between requests
    :return: dict mapping country name → output path (or None on failure)
    """
    results: dict[str, Path | None] = {}
    for i, country in enumerate(countries):
        path = scrape_country(country, output_dir=output_dir)
        results[country] = path
        if i < len(countries) - 1:
            time.sleep(delay)
    return results


# ---------------------------------------------------------------------------
# UN member states list
# ---------------------------------------------------------------------------

UN_MEMBER_STATES: list[str] = [
    "Afghanistan", "Albania", "Algeria", "Andorra", "Angola",
    "Antigua and Barbuda", "Argentina", "Armenia", "Australia", "Austria",
    "Azerbaijan", "Bahamas", "Bahrain", "Bangladesh", "Barbados",
    "Belarus", "Belgium", "Belize", "Benin", "Bhutan",
    "Bolivia", "Bosnia and Herzegovina", "Botswana", "Brazil", "Brunei",
    "Bulgaria", "Burkina Faso", "Burundi", "Cabo Verde", "Cambodia",
    "Cameroon", "Canada", "Central African Republic", "Chad", "Chile",
    "China", "Colombia", "Comoros", "Democratic Republic of the Congo",
    "Republic of the Congo", "Costa Rica", "Croatia", "Cuba", "Cyprus",
    "Czech Republic", "Denmark", "Djibouti", "Dominica", "Dominican Republic",
    "Ecuador", "Egypt", "El Salvador", "Equatorial Guinea", "Eritrea",
    "Estonia", "Eswatini", "Ethiopia", "Fiji", "Finland",
    "France", "Gabon", "Gambia", "Georgia (country)", "Germany",
    "Ghana", "Greece", "Grenada", "Guatemala", "Guinea",
    "Guinea-Bissau", "Guyana", "Haiti", "Honduras", "Hungary",
    "Iceland", "India", "Indonesia", "Iran", "Iraq",
    "Ireland", "Israel", "Italy", "Jamaica", "Japan",
    "Jordan", "Kazakhstan", "Kenya", "Kiribati", "North Korea",
    "South Korea", "Kuwait", "Kyrgyzstan", "Laos", "Latvia",
    "Lebanon", "Lesotho", "Liberia", "Libya", "Liechtenstein",
    "Lithuania", "Luxembourg", "Madagascar", "Malawi", "Malaysia",
    "Maldives", "Mali", "Malta", "Marshall Islands", "Mauritania",
    "Mauritius", "Mexico", "Federated States of Micronesia", "Moldova", "Monaco",
    "Mongolia", "Montenegro", "Morocco", "Mozambique", "Myanmar",
    "Namibia", "Nauru", "Nepal", "Netherlands", "New Zealand",
    "Nicaragua", "Niger", "Nigeria", "North Macedonia", "Norway",
    "Oman", "Pakistan", "Palau", "Panama", "Papua New Guinea",
    "Paraguay", "Peru", "Philippines", "Poland", "Portugal",
    "Qatar", "Romania", "Russia", "Rwanda", "Saint Kitts and Nevis",
    "Saint Lucia", "Saint Vincent and the Grenadines", "Samoa", "San Marino",
    "São Tomé and Príncipe", "Saudi Arabia", "Senegal", "Serbia", "Seychelles",
    "Sierra Leone", "Singapore", "Slovakia", "Slovenia", "Solomon Islands",
    "Somalia", "South Africa", "South Sudan", "Spain", "Sri Lanka",
    "Sudan", "Suriname", "Sweden", "Switzerland", "Syria",
    "Tajikistan", "Tanzania", "Thailand", "East Timor", "Togo",
    "Tonga", "Trinidad and Tobago", "Tunisia", "Turkey", "Turkmenistan",
    "Tuvalu", "Uganda", "Ukraine", "United Arab Emirates", "United Kingdom",
    "United States", "Uruguay", "Uzbekistan", "Vanuatu", "Venezuela",
    "Vietnam", "Yemen", "Zambia", "Zimbabwe",
]
