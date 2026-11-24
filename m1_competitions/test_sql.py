"""Load the M1 CSVs into an in-memory SQLite DB and run the 7 required queries."""
import sqlite3
import pandas as pd

conn = sqlite3.connect(":memory:")
pd.read_csv("data/categories.csv").to_sql("Categories", conn, index=False)
pd.read_csv("data/competitions.csv").to_sql("Competitions", conn, index=False)

QUERIES = {
    "Q1 Competitions with category name": """
        SELECT c.competition_id, c.competition_name, c.type, c.gender, cat.category_name
        FROM Competitions c LEFT JOIN Categories cat ON c.category_id = cat.category_id
        ORDER BY cat.category_name, c.competition_name""",
    "Q2 Competitions per category": """
        SELECT cat.category_id, cat.category_name, COUNT(c.competition_id) AS total_competitions
        FROM Categories cat LEFT JOIN Competitions c ON c.category_id = cat.category_id
        GROUP BY cat.category_id, cat.category_name ORDER BY total_competitions DESC""",
    "Q3 Doubles competitions": """
        SELECT competition_id, competition_name, gender, category_id
        FROM Competitions WHERE type = 'doubles' ORDER BY competition_name""",
    "Q4 ITF Men competitions": """
        SELECT c.competition_id, c.competition_name, c.type, c.gender
        FROM Competitions c JOIN Categories cat ON c.category_id = cat.category_id
        WHERE cat.category_name = 'ITF Men' ORDER BY c.competition_name""",
    "Q5 Parents and sub-competitions": """
        SELECT p.competition_name AS parent_name, s.competition_name AS sub_name, s.type, s.gender
        FROM Competitions s JOIN Competitions p ON s.parent_id = p.competition_id
        ORDER BY p.competition_name, s.competition_name""",
    "Q6 Type distribution by category": """
        SELECT cat.category_name, c.type, COUNT(*) AS total_competitions
        FROM Competitions c JOIN Categories cat ON c.category_id = cat.category_id
        GROUP BY cat.category_name, c.type ORDER BY cat.category_name, total_competitions DESC""",
    "Q7 Top-level competitions": """
        SELECT competition_id, competition_name, type, gender, category_id
        FROM Competitions WHERE parent_id IS NULL ORDER BY competition_name""",
}

for title, sql in QUERIES.items():
    df = pd.read_sql(sql, conn)
    print(f"\n=== {title}: {len(df)} rows ===")
    print(df.head(5).to_string(index=False))
