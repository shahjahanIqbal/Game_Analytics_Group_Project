# M3 - Doubles Competitor Rankings (Member 3)

This folder is the Member 3 deliverable for the *Game Analytics: Tennis Data
Explorer* project: the **Sportradar doubles competitor rankings** feed and the
**competitors** table, plus the SQL schema, the analysis queries and the
validation checks.

The pipeline turns this nested JSON:

```json
{"rankings": [{"name": "ATP", "year": 2026, "week": 31,
               "competitor_rankings": [
                 {"rank": 1, "movement": 0, "points": 9960,
                  "competitions_played": 20,
                  "competitor": {"id": "sr:competitor:14898",
                                 "name": "Heliovaara, Harri",
                                 "country": "Finland",
                                 "country_code": "FIN",
                                 "abbreviation": "HEL"}}]}]}
```

into two relational tables:

| Table | Columns |
| --- | --- |
| `competitors` | `competitor_id` (PK), `name`, `country`, `country_code`, `abbreviation` |
| `competitor_rankings` | `rank_id` (PK, identity), `rank`, `movement`, `points`, `competitions_played`, `competitor_id` (FK) |

Endpoint used:
`GET https://api.sportradar.com/tennis/{access_level}/v3/{language_code}/double_competitors_rankings.json`
(API key in the `x-api-key` header).

## Snapshot included in `data/` (2026, week 48)

| Metric | Value |
| --- | --- |
| Ranking lists | 2 (ATP men, WTA women) |
| Ranking rows | 1 000 (500 + 500) |
| Unique competitors | 1 000 |
| Countries represented | 72 |
| Tied rank groups | 12 (doubles partners sharing rank + points) |
| Rank range / points range | 1-500 / 109-11 960 |
| FK violations, duplicates, bad ranks | 0 |
| Neutral athletes (no ISO code) | 47 -> `country_code = 'NEU'` |
| Top ATP pair | Heliovaara / Patten, 8 530 points |
| Top WTA player | Siniakova, 11 960 points |

Reproduce it without an API call:
`python m3_rankings_extract.py --from-file data/raw_double_competitors_rankings.json`

**Reading the numbers:** ATP and WTA are separate ranking scales. Rank 1 exists
in both tours (three rows share rank 1: the two ATP partners plus the WTA
leader), and points are not comparable across tours. The brief's table has no
tour column, so Q6/Q7 mix both tours by design; if you add the source
`ranking_name` to `competitor_rankings`, filter on it for a per-tour board.

## Files

| File | Purpose |
| --- | --- |
| `m3_rankings_extract.py` | Fetch + flatten + clean + validate + write CSV. Standard library only. |
| `fixtures/double_competitors_rankings_sample.json` | Tiny offline fixture (2 documented rows) to dry-run without a key. **Not** the deliverable data. |
| `01_schema_competitors_rankings.sql` | Creates `competitors` and `competitor_rankings` (SQL Server; MySQL/PostgreSQL version at the bottom). |
| `02_import_competitors_rankings.sql` | Loads the two CSVs with `BULK INSERT` through staging tables (MySQL `LOAD DATA` version included). |
| `03_queries_competitors_rankings.sql` | The six required queries (Q1-Q6) + four dashboard queries (Q7-Q10). |
| `04_checks_competitors_rankings.sql` | Post-load validation checks; every "bad rows" query should return 0. |
| `data/` | Generated output (created when the script runs). |

## 1. Get a free API key (5 minutes, no payment)

Sportradar trials are free and give real data. The 403 that Member 1 hit is an
authorisation problem, not missing data.

1. Register at <https://marketplace.sportradar.com/signup> and verify your email.
2. Open the **Marketplace**, search for **Tennis**, click **Add Trial** and add it
   to your application (create one if asked).
3. Open the application: the **master API key** (40 characters) is shown there.
   Trial limits: 30 days, 1 000 requests per rolling 30 days, 1 request/second -
   this project needs a handful of requests.
4. Copy the key. Never commit it, never paste it in the group chat or in code.

If you already have a working key but get `403 Authentication Error`:

- the URL must use `trial` (this script does): a trial key on
  `/tennis/production/...` is always rejected;
- no spaces, newlines or quotes around the key value;
- the key must belong to an application that actually has the Tennis trial;
- expired trial or exhausted 30-day quota also stops returning data.

Check a key at any time without saving anything:

```powershell
$env:SPORTRADAR_API_KEY = "paste_key_here"
python m3_rankings_extract.py --check-key
```

The script prints the ranking lists it received, or a checklist explaining the
403. It never prints the key.

## 2. Run the extraction

PowerShell:

```powershell
cd m3_doubles_rankings
$env:SPORTRADAR_API_KEY = "paste_key_here"
python m3_rankings_extract.py
```

bash / zsh:

```bash
cd m3_doubles_rankings
export SPORTRADAR_API_KEY="paste_key_here"
python m3_rankings_extract.py
```

`m3_rankings_extract.py` has **no third-party dependencies**, so it runs on the
plain Python interpreter (3.9+).

No key yet? Dry-run the whole pipeline on the bundled fixture:

```powershell
python m3_rankings_extract.py --from-file fixtures/double_competitors_rankings_sample.json --out-dir sample_output
```

The fixture only contains two documented example rows, so use it to verify the
code, not as submission data.

Options:

| Option | Meaning |
| --- | --- |
| `--check-key` | Test the key only, print a diagnosis. |
| `--from-file FILE` | Build the CSVs from a saved raw JSON (team handoff / offline). |
| `--access-level trial\|production` | Default `trial`. Change only with a production key. |
| `--language en` | Feed language. |
| `--out-dir data` | Output directory. |
| `--emit-sql [--sql-dialect sqlserver\|mysql\|postgres]` | Also write `load_competitor_rankings.sql` with `INSERT` statements (no server-side file access needed). |
| `--verbose` | Debug logging. |

Outputs in `data/`:

- `raw_double_competitors_rankings.json` - untouched API response (backup)
- `competitors.csv` - 5 columns, one row per player/team
- `competitor_rankings.csv` - 5 columns, one row per ranked competitor
  (no `rank_id`: the database generates it)
- `m3_quality_report.txt` - cleaning and validation summary

## 3. Load into the database

```text
01_schema_competitors_rankings.sql      -- create tables
02_import_competitors_rankings.sql      -- copy CSVs to C:\temp\ first
04_checks_competitors_rankings.sql      -- validate
03_queries_competitors_rankings.sql     -- analysis
```

No SQL Server file access? Generate literal inserts instead:

```powershell
python m3_rankings_extract.py --emit-sql --sql-dialect sqlserver
# then run data/load_competitor_rankings.sql in SSMS
```

## 4. Cleaning rules (documented for the report)

| Rule | Reason |
| --- | --- |
| Drop rows without `competitor_id` or `name` | primary key / NOT NULL |
| Drop rows without `rank` or `points` | the row carries no ranking information |
| Missing `movement` / `competitions_played` -> `0` | NOT NULL integer columns |
| Missing `country` / `country_code` / `abbreviation` -> `Unknown` / `UNK` / `UNK` (`NEU` for neutral athletes, same as M2) | NOT NULL text columns; substitutions are counted in the report |
| `country_code` upper-cased and cut to 3 chars | `CHAR(3)` column |
| Negative points -> `0` | points cannot be negative |
| Duplicate `competitor_id` -> first row kept | primary key |
| Text trimmed, truncated to `VARCHAR` limits | schema limits |
| Tie groups (same rank + points) kept | doubles partners legitimately share a rank |

Every action is counted in `m3_quality_report.txt`, together with FK checks,
rank ranges, movement distribution and countries represented.

## 5. Required queries

| # | Requirement | Where |
| --- | --- | --- |
| 1 | All competitors with rank and points | `03_...sql` Q1 |
| 2 | Competitors ranked in the top 5 | Q2 |
| 3 | Competitors with no rank movement | Q3 |
| 4 | Total points of competitors from a specific country (Croatia) | Q4a/Q4b |
| 5 | Number of competitors per country | Q5 |
| 6 | Competitors with the highest points in the current week | Q6a/Q6b |
| + | Points ranking/GAP to leader, movers, doubles teams, country strength | Q7-Q10 |

Note: a snapshot table has one weekly load, so "current week" is the loaded
snapshot. If several weeks are ever loaded, add a `year`/`week` column to
`competitor_rankings` and filter on `MAX(week)`.

## 6. Handoff notes

**For Member 4 (database integration)**

- `competitors.csv` and `competitor_rankings.csv` have the same column names and
  order as the ones produced by `m2/transform.py`, so either source loads with
  the same schema. Load only one of them, otherwise the primary key is violated.
- Load `competitors` before `competitor_rankings` (foreign key).
- `rank_id` is an `IDENTITY` column and is intentionally absent from the CSV.
- `country_code` is `CHAR(3)`; missing values were normalised to `UNK`, and
  neutral athletes to `NEU` (same convention as `m2/transform.py`).

**For Member 5 (Streamlit)**

- Use Q5/Q10 for the country page, Q7 for the points leaderboard, Q8 for
  "biggest movers", Q9 to show doubles teams.
- Remember that partners share a rank and a shared rank skips the next number,
  so a "top 5" filter returns about five players per tour (ten rows for
  ATP + WTA), not five rows per tour. Use `DENSE_RANK() OVER (ORDER BY points
  DESC)` if the UI needs a strict 1..N position per player.

**Blocked on data?** Anyone with a working key can run the script once and share
`data/raw_double_competitors_rankings.json` (the raw response contains no key).
Everyone else runs:

```powershell
python m3_rankings_extract.py --from-file raw_double_competitors_rankings.json
```

`m2/transform.py` already references `data/raw/double_competitors_rankings.json`,
so that file may already exist on Member 2's machine - asking for it unblocks
M3 without sharing any credential.

## 7. Assumptions

- One weekly snapshot per run (the feed is published on Mondays).
- Both ATP and WTA doubles lists come back in the same call (about 500 rows
  each for a full licensed feed). The schema in the project brief has no
  tour/gender column, so the CSVs store the players only; the report records
  the list, year and week the snapshot came from.
- `rank` cannot be a primary key because doubles partners share it, hence the
  surrogate `rank_id` from the brief.
