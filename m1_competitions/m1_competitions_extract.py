"""
M1 - Competitions API extraction and cleaning.

Fetches competition data from the Sportradar Tennis API, flattens the nested
JSON into two relational tables (categories, competitions), cleans them
(missing values, duplicates, whitespace, length limits) and writes CSV files
that M4 can load into the database.

Usage:
    export SPORTRADAR_API_KEY="your_key"      # never commit this
    python m1_competitions_extract.py
    python m1_competitions_extract.py --from-file raw_competitions.json   # offline

Outputs (in ./data):
    raw_competitions.json   - untouched API response (backup)
    categories.csv          - category_id, category_name
    competitions.csv        - competition_id, competition_name, parent_id,
                              type, gender, category_id
    m1_quality_report.txt   - cleaning / validation summary
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

import pandas as pd
import requests

API_URL = "https://api.sportradar.com/tennis/trial/v3/en/competitions.json"
OUTPUT_DIR = Path("data")
MAX_RETRIES = 5
BACKOFF_SECONDS = 2
REQUEST_TIMEOUT = 30

# Column limits from the project schema
NAME_MAX = 100
ID_MAX = 50
TYPE_MAX = 20
GENDER_MAX = 10

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("m1_competitions")


def get_api_key() -> str:
    """Read the API key from the environment (keeps it out of GitHub)."""
    key = os.getenv("SPORTRADAR_API_KEY")
    if not key:
        log.error("SPORTRADAR_API_KEY environment variable is not set.")
        sys.exit(1)
    return key


def fetch_competitions(api_key: str) -> dict:
    """Call the competitions endpoint with retry/backoff for rate limits."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            # Sportradar now requires the key in the x-api-key header
            # (query-string keys stopped working from 13 Nov 2026).
            response = requests.get(
                API_URL,
                headers={"x-api-key": api_key},
                timeout=REQUEST_TIMEOUT,
            )
            if response.status_code == 429:  # rate limited (trial: 1 req/sec)
                wait = BACKOFF_SECONDS * attempt
                log.warning("Rate limited (429). Retrying in %ss...", wait)
                time.sleep(wait)
                continue
            if response.status_code in (401, 403):
                # Retrying will not help: the key/plan is the problem.
                log.error(
                    "HTTP %d: key rejected for this API. Check that the key is "
                    "for the Tennis API (trial), is active, and the URL is correct.",
                    response.status_code,
                )
                sys.exit(1)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as exc:
            # Log only the exception type so the API key in the URL is never printed
            log.error(
                "Request failed (attempt %d/%d): %s",
                attempt,
                MAX_RETRIES,
                type(exc).__name__,
            )
            time.sleep(BACKOFF_SECONDS * attempt)
    log.error("Could not fetch competitions after %d attempts.", MAX_RETRIES)
    sys.exit(1)


def check_key(api_key: str) -> None:
    """Make one request and report whether the key is accepted (key never printed)."""
    print(f"Key length: {len(api_key)}")
    try:
        response = requests.get(
            API_URL, headers={"x-api-key": api_key}, timeout=REQUEST_TIMEOUT
        )
    except requests.exceptions.RequestException as exc:
        print(f"Request failed: {type(exc).__name__}")
        sys.exit(1)

    if response.status_code == 200:
        count = len(response.json().get("competitions", []))
        print(f"OK: key accepted. Competitions returned: {count}")
    elif response.status_code in (401, 403):
        print(
            f"HTTP {response.status_code}: key rejected. Add the Tennis trial "
            "in the Sportradar marketplace and copy the key again."
        )
    elif response.status_code == 429:
        print("HTTP 429: key works but you are rate limited. Wait and retry.")
    else:
        print(f"HTTP {response.status_code}: unexpected response.")


def load_from_file(path: str) -> dict:
    """Load a previously saved raw response (useful offline / for testing)."""
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def flatten_competitions(payload: dict) -> pd.DataFrame:
    """Flatten the nested JSON into one row per competition."""
    rows = []
    for item in payload.get("competitions", []):
        category = item.get("category") or {}
        rows.append(
            {
                "competition_id": item.get("id"),
                "competition_name": item.get("name"),
                "parent_id": item.get("parent_id"),
                "type": item.get("type"),
                "gender": item.get("gender"),
                "category_id": category.get("id"),
                "category_name": category.get("name"),
            }
        )
    return pd.DataFrame(rows)


def clean_text(series: pd.Series) -> pd.Series:
    """Strip whitespace and turn empty strings into missing values."""
    return series.astype("string").str.strip().replace("", pd.NA)


def clean_data(raw: pd.DataFrame):
    """
    Clean the flat data and split it into categories and competitions.

    Rules:
      - drop rows with no competition_id or no competition_name (NOT NULL / PK)
      - missing type / gender -> 'unknown' (columns are NOT NULL)
      - missing parent_id stays NULL (top-level competition)
      - missing category -> category_id stays NULL (FK is nullable)
      - duplicates removed on the primary keys
      - values truncated to the schema's VARCHAR limits
    """
    stats = {"rows_fetched": len(raw)}
    df = raw.copy()

    for col in df.columns:
        df[col] = clean_text(df[col])

    # Missing-value report (before fixing)
    stats["missing_before"] = df.isna().sum().to_dict()

    # Rows that cannot be stored at all
    before = len(df)
    df = df.dropna(subset=["competition_id", "competition_name"])
    stats["dropped_missing_id_or_name"] = before - len(df)

    # Fill NOT NULL columns
    df["type"] = df["type"].fillna("unknown").str.lower()
    df["gender"] = df["gender"].fillna("unknown").str.lower()

    # Category name present but id missing (or the reverse) cannot be linked
    orphan_mask = df["category_id"].isna() & df["category_name"].notna()
    stats["category_name_without_id"] = int(orphan_mask.sum())

    # Duplicate competitions (primary key)
    before = len(df)
    df = df.drop_duplicates(subset=["competition_id"], keep="first")
    stats["duplicate_competitions_removed"] = before - len(df)

    # Enforce schema length limits
    df["competition_id"] = df["competition_id"].str[:ID_MAX]
    df["competition_name"] = df["competition_name"].str[:NAME_MAX]
    df["parent_id"] = df["parent_id"].str[:ID_MAX]
    df["type"] = df["type"].str[:TYPE_MAX]
    df["gender"] = df["gender"].str[:GENDER_MAX]
    df["category_id"] = df["category_id"].str[:ID_MAX]

    # Categories table (unique, id required)
    categories = (
        df[["category_id", "category_name"]]
        .dropna(subset=["category_id"])
        .drop_duplicates(subset=["category_id"], keep="first")
    )
    categories["category_name"] = categories["category_name"].fillna("Unknown")
    categories["category_name"] = categories["category_name"].str[:NAME_MAX]
    categories = categories.sort_values("category_id").reset_index(drop=True)
    stats["categories"] = len(categories)

    competitions = df[
        [
            "competition_id",
            "competition_name",
            "parent_id",
            "type",
            "gender",
            "category_id",
        ]
    ].reset_index(drop=True)
    stats["competitions"] = len(competitions)

    # Parent IDs that point to competitions not present in the data
    known_ids = set(competitions["competition_id"])
    parents = competitions["parent_id"].dropna()
    missing_parents = parents[~parents.isin(known_ids)]
    stats["parent_ids_not_in_dataset"] = int(missing_parents.nunique())

    # Category FK check
    cat_ids = set(categories["category_id"])
    cat_refs = competitions["category_id"].dropna()
    stats["category_fk_violations"] = int((~cat_refs.isin(cat_ids)).sum())

    return categories, competitions, stats


def write_report(stats: dict, path: Path) -> None:
    """Write a plain-text summary of the cleaning/validation results."""
    lines = ["M1 Competitions - data quality report", "=" * 40]
    for key, value in stats.items():
        lines.append(f"{key}: {value}")
    path.write_text("\n".join(lines), encoding="utf-8")
    log.info("Report written to %s", path)


def main() -> None:
    parser = argparse.ArgumentParser(description="M1 competitions extractor")
    parser.add_argument("--from-file", help="Use a saved raw JSON instead of the API")
    parser.add_argument(
        "--check-key",
        action="store_true",
        help="Only test whether the API key is accepted, then exit",
    )
    args = parser.parse_args()

    if args.check_key:
        check_key(get_api_key())
        return

    OUTPUT_DIR.mkdir(exist_ok=True)

    if args.from_file:
        payload = load_from_file(args.from_file)
    else:
        payload = fetch_competitions(get_api_key())
        (OUTPUT_DIR / "raw_competitions.json").write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )
        log.info("Raw response saved.")

    raw = flatten_competitions(payload)
    if raw.empty:
        log.error("No competitions found in the response.")
        sys.exit(1)

    categories, competitions, stats = clean_data(raw)

    categories.to_csv(OUTPUT_DIR / "categories.csv", index=False)
    competitions.to_csv(OUTPUT_DIR / "competitions.csv", index=False)
    write_report(stats, OUTPUT_DIR / "m1_quality_report.txt")

    log.info(
        "Done: %d categories, %d competitions.", len(categories), len(competitions)
    )


if __name__ == "__main__":
    main()
