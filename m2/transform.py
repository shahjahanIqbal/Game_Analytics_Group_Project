import json
from pathlib import Path
import pandas as pd

RAW = Path("data/raw")
OUT = Path("data/processed")
OUT.mkdir(parents=True, exist_ok=True)


def load(name):
    with open(RAW / f"{name}.json", encoding="utf-8") as f:
        return json.load(f)


def clean(df, key, text_cols=()):
    for col in text_cols:
        df[col] = df[col].astype("string").str.strip().replace("", pd.NA)
    keys = [key] if isinstance(key, str) else key
    df = df.dropna(subset=keys)
    df = df.drop_duplicates(subset=keys)
    return df.reset_index(drop=True)


# ---- categories and competitions ----
comp_rows, cat_rows = [], []
for c in load("competitions")["competitions"]:
    cat = c.get("category") or {}
    comp_rows.append({"competition_id": c.get("id"), "competition_name": c.get("name"),
                      "parent_id": c.get("parent_id"), "type": c.get("type"),
                      "gender": c.get("gender"), "category_id": cat.get("id")})
    cat_rows.append({"category_id": cat.get("id"), "category_name": cat.get("name")})

categories = clean(pd.DataFrame(cat_rows), "category_id", ["category_name"])
competitions = clean(pd.DataFrame(comp_rows), "competition_id",
                     ["competition_name", "parent_id", "type", "gender"])

# ---- complexes and venues ----
cx_rows, venue_rows = [], []
for cx in load("complexes")["complexes"]:
    cx_rows.append({"complex_id": cx.get("id"), "complex_name": cx.get("name")})
    for v in cx.get("venues") or []:
        venue_rows.append({"venue_id": v.get("id"), "venue_name": v.get("name"),
                           "city_name": v.get("city_name"),
                           "country_name": v.get("country_name"),
                           "country_code": v.get("country_code"),
                           "timezone": v.get("timezone"), "complex_id": cx.get("id")})

complexes = clean(pd.DataFrame(cx_rows), "complex_id", ["complex_name"])
venues = clean(pd.DataFrame(venue_rows), "venue_id",
               ["venue_name", "city_name", "country_name", "country_code", "timezone"])

# ---- competitors and doubles rankings ----
rank_rows, person_rows = [], []
for r in load("double_competitors_rankings")["rankings"]:
    for e in r.get("competitor_rankings") or []:
        p = e.get("competitor") or {}
        rank_rows.append({"type_id": r.get("type_id"), "ranking_name": r.get("name"),
                          "year": r.get("year"), "week": r.get("week"),
                          "gender": r.get("gender"), "rank": e.get("rank"),
                          "movement": e.get("movement"), "points": e.get("points"),
                          "competitions_played": e.get("competitions_played"),
                          "competitor_id": p.get("id")})
        person_rows.append({"competitor_id": p.get("id"), "name": p.get("name"),
                            "country": p.get("country"), "country_code": p.get("country_code"),
                            "abbreviation": p.get("abbreviation")})

competitors = clean(pd.DataFrame(person_rows), "competitor_id",
                    ["name", "country", "country_code", "abbreviation"])
# 48 players compete as "Neutral" and have no ISO code; the schema requires NOT NULL
competitors["country_code"] = competitors["country_code"].fillna("NEU")

# one row per player per ranking list (ATP/WTA), then keep only the columns in the spec
competitor_rankings = clean(pd.DataFrame(rank_rows), ["type_id", "year", "week", "competitor_id"])
competitor_rankings = competitor_rankings[
    ["rank", "movement", "points", "competitions_played", "competitor_id"]]
for col in ["rank", "movement", "points", "competitions_played"]:
    competitor_rankings[col] = competitor_rankings[col].astype("Int64")

# ---- fix broken links ----
bad = ~competitions["category_id"].isin(categories["category_id"]) & competitions["category_id"].notna()
print("competitions with unknown category:", bad.sum())
competitions.loc[bad, "category_id"] = pd.NA

bad = ~venues["complex_id"].isin(complexes["complex_id"])
print("venues with unknown complex:", bad.sum())
venues = venues[~bad]

bad = ~competitor_rankings["competitor_id"].isin(competitors["competitor_id"])
print("rankings with unknown competitor:", bad.sum())
competitor_rankings = competitor_rankings[~bad]

# ---- save ----
tables = {"categories": categories, "competitions": competitions, "complexes": complexes,
          "venues": venues, "competitors": competitors,
          "competitor_rankings": competitor_rankings}
for name, df in tables.items():
    df.to_csv(OUT / f"{name}.csv", index=False, encoding="utf-8")
    print(f"{name}: {len(df)} rows | nulls: {df.isna().sum().to_dict()}")