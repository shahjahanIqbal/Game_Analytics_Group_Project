"""Offline CSV preflight and live SQL Server post-load validation."""
import argparse
from pathlib import Path
from database.load_data import prepare_data
from database.connection import get_connection

ROOT=Path(__file__).resolve().parents[1]

def validate_database():
    expected={"categories":18,"competitions":6743,"complexes":787,"venues":4181,
              "competitors":1000,"competitor_rankings":1000}
    checks={
      "competition category orphans":"SELECT COUNT(*) FROM dbo.competitions c LEFT JOIN dbo.categories x ON x.category_id=c.category_id WHERE c.category_id IS NOT NULL AND x.category_id IS NULL",
      "competition parent orphans":"SELECT COUNT(*) FROM dbo.competitions c LEFT JOIN dbo.competitions p ON p.competition_id=c.parent_id WHERE c.parent_id IS NOT NULL AND p.competition_id IS NULL",
      "venue complex orphans":"SELECT COUNT(*) FROM dbo.venues v LEFT JOIN dbo.complexes x ON x.complex_id=v.complex_id WHERE v.complex_id IS NOT NULL AND x.complex_id IS NULL",
      "ranking competitor orphans":"SELECT COUNT(*) FROM dbo.competitor_rankings r LEFT JOIN dbo.competitors c ON c.competitor_id=r.competitor_id WHERE c.competitor_id IS NULL",
      "duplicate competitor ranking rows":"SELECT COUNT(*) FROM (SELECT competitor_id FROM dbo.competitor_rankings GROUP BY competitor_id HAVING COUNT(*)>1) d",
      "invalid ranking values":"SELECT COUNT(*) FROM dbo.competitor_rankings WHERE [rank]<1 OR [rank]>500 OR points<0 OR competitions_played<0",
    }
    conn=get_connection(); out=[]
    try:
      cur=conn.cursor()
      for t,n in expected.items():
        cur.execute(f"SELECT COUNT(*) FROM dbo.[{t}]"); actual=cur.fetchone()[0]
        out.append(f"{'OK' if actual==n else 'CHECK'} {t}: {actual} (expected {n})")
      for label,sql in checks.items():
        cur.execute(sql); n=cur.fetchone()[0]
        out.append(f"{'OK' if n==0 else 'FAIL'} {label}: {n}")
    finally: conn.close()
    return out

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--csv-dir",type=Path,default=ROOT/"data")
    p.add_argument("--db",action="store_true")
    a=p.parse_args()
    _,report=prepare_data(a.csv_dir)
    print("CSV preflight:",report)
    if a.db:
      print("DATABASE CHECKS")
      for line in validate_database(): print(line)

if __name__=="__main__": main()
