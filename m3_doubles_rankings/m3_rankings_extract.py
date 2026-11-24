#!/usr/bin/env python3
"""
M3 - Doubles competitor rankings and competitors extraction.

Fetches the Sportradar Tennis "Doubles Competitor Rankings" feed, flattens the
nested JSON into two relational tables (competitors, competitor_rankings),
cleans the data (missing values, duplicates, whitespace, length limits),
validates the result and writes CSV files that M4 can load into the database.

Endpoint:
    https://api.sportradar.com/tennis/{access_level}/v3/{language_code}/
        double_competitors_rankings.json

The API key is read from the SPORTRADAR_API_KEY environment variable and is
sent in the x-api-key header. The key is never printed, logged or written to
disk.

Usage (PowerShell):
    $env:SPORTRADAR_API_KEY = "your_key"        # never commit this
    python m3_rankings_extract.py               # fetch + clean + write CSV
    python m3_rankings_extract.py --check-key   # only test the key
    python m3_rankings_extract.py --from-file raw_double_competitors_rankings.json

Usage (bash / macOS / Linux):
    export SPORTRADAR_API_KEY="your_key"
    python m3_rankings_extract.py

Outputs (in ./data):
    raw_double_competitors_rankings.json - untouched API response (backup)
    competitors.csv                      - competitor_id, name, country,
                                           country_code, abbreviation
    competitor_rankings.csv              - rank, movement, points,
                                           competitions_played, competitor_id
    m3_quality_report.txt                - cleaning / validation summary

Optional:
    --emit-sql writes load_competitor_rankings.sql (literal INSERT statements)
    which loads the CSVs into any SQL database without BULK LOAD / LOAD DATA.

Only the Python standard library is used, so there is nothing to pip install.
"""

import argparse
import csv
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

API_HOST = "https://api.sportradar.com"
ENDPOINT_PATH = (
    "/tennis/{access_level}/v3/{language_code}/double_competitors_rankings.json"
)
DEFAULT_OUT_DIR = Path("data")
DEFAULT_FIXTURE = Path(__file__).resolve().parent / "fixtures" / (
    "double_competitors_rankings_sample.json"
)

MAX_ATTEMPTS = 5
BACKOFF_SECONDS = 3
REQUEST_TIMEOUT = 30

# Column limits from the project schema
ID_MAX = 50
NAME_MAX = 100
COUNTRY_MAX = 100
COUNTRY_CODE_MAX = 3
ABBREVIATION_MAX = 10
RANK_MAX = 500  # the feed returns the top 500 of each tour

COMPETITOR_COLUMNS = [
    "competitor_id",
    "name",
    "country",
    "country_code",
    "abbreviation",
]
RANKING_COLUMNS = ["rank", "movement", "points", "competitions_played", "competitor_id"]

log = logging.getLogger("m3_rankings")

AUTH_HELP = """\
How to fix a 403 "Authentication Error" from Sportradar:

  1. The key must belong to an application that has an ACTIVE Tennis trial.
     Get one free at https://marketplace.sportradar.com/signup
     (Add Trial -> search "Tennis" -> add it to your application).
     Trial limits: 30 days, 1000 requests per rolling 30 days, 1 request/sec.
  2. The key and the URL access level must match. A trial key only works with
     /tennis/trial/... (the default here). Calling /tennis/production/... with
     a trial key always returns 403.
  3. Copy the key again from the console: new master keys are 40 characters,
     legacy keys are 24. A trailing space, newline or quote around the value
     in $env:SPORTRADAR_API_KEY also causes 403. If a 24-character legacy key
     fails, create a new application in the console and use its master key.
  4. Send the key in the x-api-key header (this script does that). A key in
     the URL query string is no longer accepted.
  5. Expired trials and exhausted 30-day quotas stop returning data.
  6. If a teammate's key works and yours does not, you are probably looking at
     a different application in the console.
The key is never printed or logged by this script.
"""


class SportradarError(RuntimeError):
    """Base class for extraction errors."""


class AuthError(SportradarError):
    """The API key was rejected (HTTP 401/403). Never retried."""

    def __init__(self, message: str, status: int) -> None:
        super().__init__(message)
        self.status = status


class ApiError(SportradarError):
    """The API could not be reached or returned an unexpected response."""


# ---------------------------------------------------------------------------
# API access
# ---------------------------------------------------------------------------
def build_url(access_level: str, language_code: str) -> str:
    """Build the endpoint URL for the requested access level and language."""
    if access_level not in ("trial", "production"):
        raise ValueError("access_level must be 'trial' or 'production'")
    path = ENDPOINT_PATH.format(
        access_level=access_level, language_code=language_code
    )
    return API_HOST + path


def get_api_key() -> str:
    """Read the API key from the environment (keeps it out of GitHub)."""
    key = (os.getenv("SPORTRADAR_API_KEY") or "").strip()
    if not key:
        raise SystemExit(
            "SPORTRADAR_API_KEY is not set.\n"
            "  PowerShell: $env:SPORTRADAR_API_KEY = \"your_key\"\n"
            "  bash:       export SPORTRADAR_API_KEY=\"your_key\"\n"
            f"No key yet? Run with a saved response instead:\n"
            f"  python {Path(sys.argv[0]).name} --from-file "
            f"{DEFAULT_FIXTURE.as_posix()}"
        )
    return key


def _retry_delay(exc: urllib.error.HTTPError, attempt: int) -> int:
    """Honour Retry-After when present, otherwise use linear backoff."""
    retry_after = None
    if exc.headers is not None:
        retry_after = exc.headers.get("Retry-After")
    if retry_after and retry_after.isdigit():
        return max(int(retry_after), 1)
    return BACKOFF_SECONDS * attempt


def fetch_payload(url: str, api_key: str) -> Dict[str, Any]:
    """
    Call the rankings endpoint and return the decoded JSON payload.

    Retries 429 (throttled), 5xx and network failures with backoff.
    Raises AuthError immediately on 401/403 because retrying cannot help.
    """
    headers = {
        "accept": "application/json",
        "x-api-key": api_key,
        "user-agent": "m3-doubles-rankings/1.0 (student project)",
    }

    for attempt in range(1, MAX_ATTEMPTS + 1):
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                raw = response.read().decode("utf-8")
            return json.loads(raw)
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise AuthError(
                    f"HTTP {exc.code} Authentication Error from Sportradar.",
                    exc.code,
                ) from None
            if exc.code == 429:
                wait = _retry_delay(exc, attempt)
                log.warning(
                    "HTTP 429 (throttled or quota reached). Retrying in %ds (%d/%d).",
                    wait,
                    attempt,
                    MAX_ATTEMPTS,
                )
                time.sleep(wait)
                continue
            if 500 <= exc.code < 600:
                wait = BACKOFF_SECONDS * attempt
                log.warning(
                    "HTTP %d from the server. Retrying in %ds (%d/%d).",
                    exc.code,
                    wait,
                    attempt,
                    MAX_ATTEMPTS,
                )
                time.sleep(wait)
                continue
            # 400/404/405 etc. are request problems, not temporary failures.
            raise ApiError(
                f"HTTP {exc.code} for {url}. Check the access level, language "
                "code and endpoint spelling."
            ) from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            wait = BACKOFF_SECONDS * attempt
            log.warning(
                "Network error (%s). Retrying in %ds (%d/%d).",
                type(exc).__name__,
                wait,
                attempt,
                MAX_ATTEMPTS,
            )
            time.sleep(wait)
        except json.JSONDecodeError:
            log.warning(
                "Response was not valid JSON (%d/%d), retrying.",
                attempt,
                MAX_ATTEMPTS,
            )
            time.sleep(BACKOFF_SECONDS)

    raise ApiError(
        f"Giving up after {MAX_ATTEMPTS} attempts. "
        "If the status was 429, the key's 30-day quota may be exhausted."
    )


def check_key(url: str, api_key: str) -> int:
    """Fetch once and print a human-readable diagnosis. Returns an exit code."""
    log.info("Testing %s", url)
    try:
        payload = fetch_payload(url, api_key)
    except AuthError as exc:
        log.error("%s", exc)
        print(AUTH_HELP)
        return 2
    except ApiError as exc:
        log.error("%s", exc)
        return 1

    lists = payload.get("rankings") or []
    rows = sum(len(item.get("competitor_rankings") or []) for item in lists)
    print("Key OK.")
    print(f"  ranking lists : {len(lists)}")
    print(f"  ranking rows  : {rows}")
    print(f"  generated_at  : {payload.get('generated_at')}")
    for item in lists:
        print(
            "  - {name} ({gender}) {year} week {week}: {count} rows".format(
                name=item.get("name"),
                gender=item.get("gender"),
                year=item.get("year"),
                week=item.get("week"),
                count=len(item.get("competitor_rankings") or []),
            )
        )
    return 0


# ---------------------------------------------------------------------------
# Transformation
# ---------------------------------------------------------------------------
def load_from_file(path: str) -> Dict[str, Any]:
    """Load a previously saved raw response (offline mode / teammate handoff)."""
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def flatten_payload(
    payload: Dict[str, Any]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Flatten the nested JSON into one row per ranked competitor.

    Returns (rows, ranking_lists). Each row keeps the ranking context
    (ranking_name, gender, year, week) so the data can be validated per tour;
    those helper fields are dropped before the CSV files are written.
    """
    rows: List[Dict[str, Any]] = []
    ranking_lists: List[Dict[str, Any]] = []

    for ranking in payload.get("rankings") or []:
        ranking_lists.append(
            {
                "name": ranking.get("name"),
                "type_id": ranking.get("type_id"),
                "gender": ranking.get("gender"),
                "year": ranking.get("year"),
                "week": ranking.get("week"),
                "rows": len(ranking.get("competitor_rankings") or []),
            }
        )
        for entry in ranking.get("competitor_rankings") or []:
            competitor = entry.get("competitor") or {}
            rows.append(
                {
                    "rank": entry.get("rank"),
                    "movement": entry.get("movement"),
                    "points": entry.get("points"),
                    "competitions_played": entry.get("competitions_played"),
                    # The feed exposes the id both on the ranking entry and
                    # inside the competitor object; prefer the competitor one.
                    "competitor_id": competitor.get("id") or entry.get("competitor_id"),
                    "name": competitor.get("name") or entry.get("name"),
                    "country": competitor.get("country"),
                    "country_code": competitor.get("country_code"),
                    "abbreviation": competitor.get("abbreviation"),
                    "ranking_name": ranking.get("name"),
                    "gender": ranking.get("gender"),
                    "year": ranking.get("year"),
                    "week": ranking.get("week"),
                }
            )
    return rows, ranking_lists


def clean_text(value: Any, max_length: Optional[int] = None) -> Optional[str]:
    """Strip whitespace, turn empty strings into None and enforce length."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:max_length] if max_length else text


def to_int(value: Any) -> Optional[int]:
    """Convert an API value to int, returning None when it is not numeric."""
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def count_truncations(rows: List[Dict[str, Any]]) -> int:
    """Count values that are longer than their VARCHAR column allows."""
    limits = {
        "competitor_id": ID_MAX,
        "name": NAME_MAX,
        "country": COUNTRY_MAX,
        "abbreviation": ABBREVIATION_MAX,
        "country_code": COUNTRY_CODE_MAX,
    }
    truncated = 0
    for row in rows:
        for field, limit in limits.items():
            value = clean_text(row.get(field))
            if value is not None and len(value) > limit:
                truncated += 1
    return truncated


def clean_data(
    rows: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    """
    Clean the flat rows and split them into the two relational tables.

    Rules:
      - competitor_id and name are required (PK / NOT NULL) -> drop the row
      - rank and points are required (the whole point of the table) -> drop
      - movement / competitions_played missing -> 0 (NOT NULL columns)
      - missing country fields get an explicit placeholder so the NOT NULL
        constraints hold; every substitution is counted in the report
      - duplicate competitor_ids are removed (first occurrence wins)
      - text values are trimmed and truncated to the VARCHAR limits
    """
    stats: Dict[str, Any] = {"rows_fetched": len(rows)}
    missing_fields = [
        "competitor_id",
        "name",
        "rank",
        "points",
        "movement",
        "competitions_played",
        "country",
        "country_code",
        "abbreviation",
    ]
    for field in missing_fields:
        stats[f"missing_{field}"] = sum(
            1 for row in rows if clean_text(row.get(field)) is None
        )

    kept: List[Dict[str, Any]] = []
    dropped_key = 0
    dropped_rank = 0

    for row in rows:
        competitor_id = clean_text(row.get("competitor_id"), ID_MAX)
        name = clean_text(row.get("name"), NAME_MAX)
        rank = to_int(row.get("rank"))
        points = to_int(row.get("points"))

        if not competitor_id or not name:
            dropped_key += 1
            continue
        if rank is None or points is None:
            dropped_rank += 1
            continue

        kept.append(
            {
                "competitor_id": competitor_id,
                "name": name,
                "country": clean_text(row.get("country"), COUNTRY_MAX),
                "country_code": clean_text(row.get("country_code")),
                "abbreviation": clean_text(row.get("abbreviation"), ABBREVIATION_MAX),
                "rank": rank,
                "points": points,
                "movement": to_int(row.get("movement")),
                "competitions_played": to_int(row.get("competitions_played")),
                "ranking_name": row.get("ranking_name"),
                "gender": row.get("gender"),
                "year": row.get("year"),
                "week": row.get("week"),
            }
        )

    stats["dropped_missing_competitor_id_or_name"] = dropped_key
    stats["dropped_missing_rank_or_points"] = dropped_rank

    # NOT NULL defaults for the numeric columns
    stats["filled_movement"] = sum(1 for row in kept if row["movement"] is None)
    stats["filled_competitions_played"] = sum(
        1 for row in kept if row["competitions_played"] is None
    )
    for row in kept:
        row["movement"] = row["movement"] if row["movement"] is not None else 0
        row["competitions_played"] = (
            row["competitions_played"]
            if row["competitions_played"] is not None
            else 0
        )

    # NOT NULL defaults for the text columns
    stats["filled_country"] = sum(1 for row in kept if row["country"] is None)
    stats["filled_country_code"] = sum(1 for row in kept if row["country_code"] is None)
    stats["filled_abbreviation"] = sum(
        1 for row in kept if row["abbreviation"] is None
    )
    for row in kept:
        row["country"] = row["country"] or "Unknown"
        if not row["country_code"]:
            # Neutral athletes have no ISO code; M2's transform uses NEU for
            # them, so keep both pipelines consistent.
            is_neutral = (row["country"] or "").lower().startswith("neutral")
            row["country_code"] = "NEU" if is_neutral else "UNK"
        row["country_code"] = row["country_code"].upper()[:COUNTRY_CODE_MAX]
        row["abbreviation"] = row["abbreviation"] or "UNK"

    # Negative points are impossible: clamp and report.
    stats["negative_points_fixed"] = sum(1 for row in kept if row["points"] < 0)
    for row in kept:
        if row["points"] < 0:
            row["points"] = 0

    # One competitor per row (PK), one ranking row per competitor per snapshot
    stats["truncated_values"] = count_truncations(rows)

    before = len(kept)
    kept = _dedupe(kept, "competitor_id")
    stats["duplicate_competitors_removed"] = before - len(kept)

    # Build the parent table first so the FK target exists
    competitors = _build_competitors(kept)
    rankings = _build_rankings(kept)
    stats["competitors"] = len(competitors)
    stats["competitor_rankings"] = len(rankings)

    return competitors, rankings, stats


def _dedupe(rows: List[Dict[str, Any]], key: str) -> List[Dict[str, Any]]:
    """Remove duplicate rows on a single key, keeping the first occurrence."""
    seen = set()
    unique: List[Dict[str, Any]] = []
    for row in rows:
        value = row.get(key)
        if value in seen:
            continue
        seen.add(value)
        unique.append(row)
    return unique


def _build_competitors(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Project the flat rows into the Competitors table."""
    competitors = []
    for row in rows:
        competitors.append(
            {
                "competitor_id": row["competitor_id"],
                "name": row["name"],
                "country": row["country"],
                "country_code": row["country_code"],
                "abbreviation": row["abbreviation"],
            }
        )
    competitors = _dedupe(competitors, "competitor_id")
    competitors.sort(key=lambda item: item["competitor_id"])
    return competitors


def _build_rankings(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Project the flat rows into the Competitor_Rankings table."""
    rankings = []
    for row in rows:
        rankings.append(
            {
                "rank": row["rank"],
                "movement": row["movement"],
                "points": row["points"],
                "competitions_played": row["competitions_played"],
                "competitor_id": row["competitor_id"],
            }
        )
    rankings = _dedupe(rankings, "competitor_id")
    # Doubles partners share a rank, so sort by rank then points then id.
    rankings.sort(
        key=lambda item: (item["rank"], -item["points"], item["competitor_id"])
    )
    return rankings


def validate(
    rows: List[Dict[str, Any]],
    competitors: List[Dict[str, Any]],
    rankings: List[Dict[str, Any]],
    ranking_lists: List[Dict[str, Any]],
    stats: Dict[str, Any],
) -> Dict[str, Any]:
    """Run consistency checks and add the results to the report."""
    stats["ranking_lists"] = len(ranking_lists)
    stats["lists_detail"] = "; ".join(
        "{name} ({gender}, {year} week {week}): {rows} rows".format(**item)
        for item in ranking_lists
    )
    stats["snapshot"] = ", ".join(
        sorted(
            {
                "{} - week {}".format(item.get("year"), item.get("week"))
                for item in ranking_lists
            }
        )
    )

    known_ids = {competitor["competitor_id"] for competitor in competitors}
    stats["fk_violations"] = sum(
        1 for row in rankings if row["competitor_id"] not in known_ids
    )
    stats["competitors_without_ranking"] = len(
        known_ids - {row["competitor_id"] for row in rankings}
    )

    stats["ranks_below_1"] = sum(1 for row in rankings if row["rank"] < 1)
    stats["ranks_above_500"] = sum(1 for row in rankings if row["rank"] > RANK_MAX)
    stats["negative_movement"] = sum(1 for row in rankings if row["movement"] < 0)
    stats["positive_movement"] = sum(1 for row in rankings if row["movement"] > 0)
    stats["stable_movement"] = sum(1 for row in rankings if row["movement"] == 0)

    stats["countries_represented"] = len({row["country_code"] for row in competitors})
    stats["highest_points"] = max((row["points"] for row in rankings), default=0)
    stats["lowest_points"] = min((row["points"] for row in rankings), default=0)

    # Players sharing rank + points inside the same tour are doubles partners.
    tie_groups = {}
    for row in rows:
        group = (
            row.get("ranking_name"),
            to_int(row.get("rank")),
            to_int(row.get("points")),
        )
        tie_groups.setdefault(group, []).append(row.get("competitor_id"))
    stats["tie_groups"] = sum(1 for ids in tie_groups.values() if len(ids) > 1)

    # Within one tour, points must not increase as the rank number increases.
    violations = 0
    for item in ranking_lists:
        tour_rows: List[Tuple[int, int]] = []
        for row in rows:
            if row.get("ranking_name") != item.get("name"):
                continue
            rank = to_int(row.get("rank"))
            points = to_int(row.get("points"))
            if rank is None or points is None:
                continue
            tour_rows.append((rank, points))
        tour_rows.sort()
        for (rank_a, points_a), (rank_b, points_b) in zip(
            tour_rows, tour_rows[1:]
        ):
            if rank_b > rank_a and points_b > points_a:
                violations += 1
    stats["rank_points_order_violations"] = violations

    return stats


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
def write_csv(rows: List[Dict[str, Any]], columns: List[str], path: Path) -> None:
    """Write a list of dictionaries as a UTF-8 CSV with a header row."""
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def write_report(stats: Dict[str, Any], path: Path, source: str) -> None:
    """Write a plain-text summary of the cleaning and validation results."""
    lines = [
        "M3 Doubles Competitor Rankings - data quality report",
        "=" * 54,
        f"generated_at: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"source: {source}",
        "",
        "Cleaning",
        "-" * 54,
    ]
    cleaning_keys = [
        "rows_fetched",
        "dropped_missing_competitor_id_or_name",
        "dropped_missing_rank_or_points",
        "filled_movement",
        "filled_competitions_played",
        "filled_country",
        "filled_country_code",
        "filled_abbreviation",
        "negative_points_fixed",
        "truncated_values",
        "duplicate_competitors_removed",
        "competitors",
        "competitor_rankings",
    ]
    lines += [f"{key}: {stats.get(key)}" for key in cleaning_keys]

    lines += ["", "Missing values in the raw response", "-" * 54]
    lines += [
        f"{key}: {value}"
        for key, value in stats.items()
        if key.startswith("missing_")
    ]

    lines += ["", "Snapshot", "-" * 54]
    lines += [
        f"ranking_lists: {stats.get('ranking_lists')}",
        f"snapshot: {stats.get('snapshot')}",
        f"lists_detail: {stats.get('lists_detail')}",
    ]

    lines += ["", "Validation", "-" * 54]
    validation_keys = [
        "fk_violations",
        "competitors_without_ranking",
        "ranks_below_1",
        "ranks_above_500",
        "rank_points_order_violations",
        "tie_groups",
        "stable_movement",
        "positive_movement",
        "negative_movement",
        "countries_represented",
        "highest_points",
        "lowest_points",
    ]
    lines += [f"{key}: {stats.get(key)}" for key in validation_keys]

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log.info("Report written to %s", path)


def _sql_literal(value: Any, dialect: str = "sqlserver") -> str:
    """Render a Python value as a SQL literal for the requested dialect."""
    if value is None:
        return "NULL"
    if isinstance(value, int):
        return str(value)
    text = str(value).replace("'", "''")
    if dialect == "sqlserver":
        return "N'" + text + "'"
    return "'" + text + "'"


def _sql_identifier(name: str, dialect: str) -> str:
    """Quote an identifier so reserved words such as `rank` stay usable."""
    if dialect == "mysql":
        return f"`{name}`"
    if dialect == "postgres":
        return f'"{name}"'
    return f"[{name}]"


def write_load_sql(
    competitors: List[Dict[str, Any]],
    rankings: List[Dict[str, Any]],
    path: Path,
    dialect: str = "sqlserver",
    batch_size: int = 200,
) -> None:
    """
    Write literal INSERT statements as an alternative to BULK INSERT.

    Useful when the database server cannot read a file path (BULK INSERT /
    LOAD DATA need server-side file access).
    """
    competitor_columns = ", ".join(
        _sql_identifier(column, dialect) for column in COMPETITOR_COLUMNS
    )
    ranking_columns = ", ".join(
        _sql_identifier(column, dialect) for column in RANKING_COLUMNS
    )
    lines = [
        "-- Generated by m3_rankings_extract.py",
        f"-- Dialect: {dialect}",
        "-- Data snapshot: "
        + datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "-- Run the schema script first; competitors before rankings (FK).",
        "",
    ]
    for start in range(0, len(competitors), batch_size):
        batch = competitors[start : start + batch_size]
        lines.append(
            f"INSERT INTO competitors ({competitor_columns}) VALUES"
        )
        values = [
            "({}, {}, {}, {}, {})".format(
                _sql_literal(row["competitor_id"], dialect),
                _sql_literal(row["name"], dialect),
                _sql_literal(row["country"], dialect),
                _sql_literal(row["country_code"], dialect),
                _sql_literal(row["abbreviation"], dialect),
            )
            for row in batch
        ]
        lines.append(",\n".join(values) + ";")
        lines.append("")

    for start in range(0, len(rankings), batch_size):
        batch = rankings[start : start + batch_size]
        lines.append(
            f"INSERT INTO competitor_rankings ({ranking_columns}) VALUES"
        )
        values = [
            "({}, {}, {}, {}, {})".format(
                row["rank"],
                row["movement"],
                row["points"],
                row["competitions_played"],
                _sql_literal(row["competitor_id"], dialect),
            )
            for row in batch
        ]
        lines.append(",\n".join(values) + ";")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    log.info("SQL load script written to %s", path)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Extract Sportradar doubles competitor rankings (M3)."
    )
    parser.add_argument(
        "--from-file",
        help="Use a saved raw JSON response instead of calling the API",
    )
    parser.add_argument(
        "--access-level",
        choices=("trial", "production"),
        default="trial",
        help="Sportradar access level matching your key (default: trial)",
    )
    parser.add_argument(
        "--language",
        default="en",
        help="Language code of the feed (default: en)",
    )
    parser.add_argument(
        "--out-dir",
        default=str(DEFAULT_OUT_DIR),
        help="Directory for the generated files (default: data)",
    )
    parser.add_argument(
        "--check-key",
        action="store_true",
        help="Only test the API key and print a diagnosis",
    )
    parser.add_argument(
        "--emit-sql",
        action="store_true",
        help="Also write load_competitor_rankings.sql with INSERT statements",
    )
    parser.add_argument(
        "--sql-dialect",
        choices=("sqlserver", "mysql", "postgres"),
        default="sqlserver",
        help="Dialect used by --emit-sql (default: sqlserver)",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Enable debug logging"
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    """Run the extraction pipeline."""
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    url = build_url(args.access_level, args.language)

    if args.check_key:
        return check_key(url, get_api_key())

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.from_file:
        source = Path(args.from_file).resolve().as_uri()
        log.info("Reading saved response %s", args.from_file)
        try:
            payload = load_from_file(args.from_file)
        except (OSError, json.JSONDecodeError) as exc:
            log.error("Could not read %s (%s).", args.from_file, type(exc).__name__)
            return 1
    else:
        source = url
        payload = fetch_payload(url, get_api_key())
        raw_path = out_dir / "raw_double_competitors_rankings.json"
        raw_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        log.info("Raw response saved to %s", raw_path)

    rows, ranking_lists = flatten_payload(payload)
    if not rows:
        log.error("No competitor rankings found in the response.")
        return 1

    competitors, rankings, stats = clean_data(rows)
    stats = validate(rows, competitors, rankings, ranking_lists, stats)

    write_csv(competitors, COMPETITOR_COLUMNS, out_dir / "competitors.csv")
    write_csv(rankings, RANKING_COLUMNS, out_dir / "competitor_rankings.csv")
    write_report(stats, out_dir / "m3_quality_report.txt", source)
    if args.emit_sql:
        write_load_sql(
            competitors,
            rankings,
            out_dir / "load_competitor_rankings.sql",
            dialect=args.sql_dialect,
        )

    log.info(
        "Done: %d competitors, %d ranking rows (%s).",
        stats["competitors"],
        stats["competitor_rankings"],
        stats["snapshot"],
    )
    if stats["fk_violations"]:
        log.warning("Foreign key violations: %d", stats["fk_violations"])
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AuthError as error:
        log.error("%s", error)
        print(AUTH_HELP)
        sys.exit(2)
    except SportradarError as error:
        log.error("%s", error)
        sys.exit(1)
