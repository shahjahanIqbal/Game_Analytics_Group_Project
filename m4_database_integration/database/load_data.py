"""CSV validation and atomic six-table loader for SQL Server."""
import argparse, csv, json
from pathlib import Path
from database.connection import get_connection

ROOT = Path(__file__).resolve().parents[1]
TABLES = {
 "categories": (["category_id","category_name"],["category_id","category_name"]),
 "competitions": (["competition_id","competition_name","parent_id","type","gender","category_id"],
                  ["competition_id","competition_name","type","gender"]),
 "complexes": (["complex_id","complex_name"],["complex_id","complex_name"]),
 "venues": (["venue_id","venue_name","city_name","country_name","country_code","timezone","complex_id"],
            ["venue_id","venue_name","city_name","country_name","country_code","timezone"]),
 "competitors": (["competitor_id","name","country","country_code","abbreviation"],
                 ["competitor_id","name","country","country_code","abbreviation"]),
 "competitor_rankings": (["rank","movement","points","competitions_played","competitor_id"],
                         ["rank","movement","points","competitions_played","competitor_id"]),
}
ORDER = ["categories","competitions","complexes","venues","competitors","competitor_rankings"]
DELETE_ORDER = ["competitor_rankings","competitors","venues","complexes","competitions","categories"]

def read_table(folder, table):
    columns, required = TABLES[table]
    path = folder / f"{table}.csv"
    with path.open(encoding="utf-8-sig",newline="") as f:
        reader=csv.DictReader(f)
        if reader.fieldnames is None or set(columns)-set(reader.fieldnames):
            raise ValueError(f"{path.name}: expected columns {columns}; found {reader.fieldnames}")
        result=[]
        for n,raw in enumerate(reader,start=2):
            row={c:((raw.get(c) or "").strip() or None) for c in columns}
            for c in required:
                if row[c] is None: raise ValueError(f"{path.name}:{n}: {c} is required")
            result.append(row)
    return result

def unique(rows, table, key):
    seen=set()
    for row in rows:
        if row[key] in seen: raise ValueError(f"{table}: duplicate {key}={row[key]}")
        seen.add(row[key])

def prepare_data(folder):
    data={t:read_table(folder,t) for t in ORDER}
    for t,k in [("categories","category_id"),("competitions","competition_id"),
                ("complexes","complex_id"),("venues","venue_id"),("competitors","competitor_id")]:
        unique(data[t],t,k)
    for row in data["competitor_rankings"]:
        for c in ("rank","movement","points","competitions_played"):
            try: row[c]=int(row[c])
            except (TypeError,ValueError): raise ValueError(f"Ranking {c} must be an integer: {row[c]!r}")
        if not 1 <= row["rank"] <= 500: raise ValueError(f"Ranking out of expected 1-500 range: {row['rank']}")
        if row["points"] < 0 or row["competitions_played"] < 0:
            raise ValueError("Ranking points and competitions_played must be non-negative")
    cat_ids={r["category_id"] for r in data["categories"]}
    bad=[r["competition_id"] for r in data["competitions"] if r["category_id"] not in cat_ids]
    if bad: raise ValueError(f"{len(bad)} competitions have unknown category_id")
    comp_ids={r["competition_id"] for r in data["competitions"]}
    original=read_table(folder,"competitions")
    missing_parents={r["parent_id"] for r in original if r["parent_id"] and r["parent_id"] not in comp_ids}
    nulled=sum(1 for r in original if r["parent_id"] and r["parent_id"] not in comp_ids)
    for r in data["competitions"]:
        if r["parent_id"] not in comp_ids: r["parent_id"]=None
    complex_ids={r["complex_id"] for r in data["complexes"]}
    bad=[r["venue_id"] for r in data["venues"] if r["complex_id"] and r["complex_id"] not in complex_ids]
    if bad: raise ValueError(f"{len(bad)} venues have unknown complex_id")
    competitor_ids={r["competitor_id"] for r in data["competitors"]}
    bad=[r["competitor_id"] for r in data["competitor_rankings"] if r["competitor_id"] not in competitor_ids]
    if bad: raise ValueError(f"{len(bad)} rankings have unknown competitor_id")
    unique(data["competitor_rankings"],"competitor_rankings","competitor_id")
    report={"row_counts":{t:len(data[t]) for t in ORDER},
            "distinct_missing_parent_ids_nulled":len(missing_parents),
            "competition_parent_rows_nulled":nulled,
            "valid_parent_links_preserved":sum(bool(r["parent_id"]) for r in data["competitions"])}
    return data,report

def split_go(sql):
    batches=[]; current=[]
    for line in sql.splitlines():
        if line.strip().upper()=="GO":
            if "\n".join(current).strip(): batches.append("\n".join(current).strip())
            current=[]
        else: current.append(line)
    if "\n".join(current).strip(): batches.append("\n".join(current).strip())
    return batches

def initialize_schema():
    schema=(ROOT/"sql"/"schema.sql").read_text(encoding="utf-8")
    conn=get_connection("master", autocommit=True)
    try:
        cur=conn.cursor()
        for batch in split_go(schema):
            cur.execute(batch)
        print("Schema initialized in tennis_db.")
    except Exception:
        conn.rollback(); raise
    finally: conn.close()

def insert_rows(cur,table,rows):
    if not rows: print(f"LOADED {table}: 0 rows"); return
    cols=TABLES[table][0]
    sql=f"INSERT INTO dbo.[{table}] ({','.join('['+c+']' for c in cols)}) VALUES ({','.join('?' for _ in cols)})"
    values=[tuple(row[c] for c in cols) for row in rows]
    cur.fast_executemany=True
    cur.executemany(sql,values)
    print(f"LOADED {table}: {len(rows):,}")

def load_data(folder):
    data,report=prepare_data(folder)
    print("Pre-load checks passed:",json.dumps(report,indent=2))
    conn=get_connection()
    try:
        cur=conn.cursor()
        try:
            for t in DELETE_ORDER:
                if t == "competitions":
                    # Clear self-references before deleting the competition rows.
                    cur.execute("UPDATE dbo.competitions SET parent_id=NULL")
                cur.execute(f"DELETE FROM dbo.[{t}]")
            for t in ORDER:
                if t!="competitions":
                    insert_rows(cur,t,data[t])
                else:
                    # Insert all competitions with parent_id NULL first; then restore
                    # valid parent links once all referenced rows exist.
                    rows=[dict(r,parent_id=None) for r in data[t]]
                    insert_rows(cur,t,rows)
                    links=[(r["parent_id"],r["competition_id"]) for r in data[t] if r["parent_id"]]
                    if links:
                        cur.fast_executemany=True
                        cur.executemany("UPDATE dbo.competitions SET parent_id=? WHERE competition_id=?",links)
                        print(f"RESTORED parent links: {len(links):,}")
            conn.commit()
            print("SUCCESS: all six datasets committed.")
        except Exception:
            conn.rollback()
            raise
    finally: conn.close()

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--csv-dir",type=Path,default=ROOT/"data")
    p.add_argument("--init-schema",action="store_true")
    p.add_argument("--validate-only",action="store_true")
    a=p.parse_args()
    if a.validate_only:
        _,report=prepare_data(a.csv_dir); print(json.dumps(report,indent=2)); return
    if a.init_schema: initialize_schema()
    load_data(a.csv_dir)

if __name__=="__main__": main()
