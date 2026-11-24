-- ============================================================
-- 04_checks_competitors_rankings.sql
-- M3 - Validation checks to run after loading the CSVs
-- (SQL Server / SSMS). Every "bad rows" query should return 0.
-- ============================================================

USE tennis_db;
GO

-- ---------------------------------------------------------------------
-- 1. Row counts and basic coverage
-- ---------------------------------------------------------------------
SELECT (SELECT COUNT(*) FROM dbo.competitors)          AS competitors,
       (SELECT COUNT(*) FROM dbo.competitor_rankings)  AS ranking_rows,
       (SELECT COUNT(DISTINCT country) FROM dbo.competitors) AS countries;
GO

-- ---------------------------------------------------------------------
-- 2. Primary key: no duplicate competitor_id
-- ---------------------------------------------------------------------
SELECT competitor_id, COUNT(*) AS duplicate_rows
FROM dbo.competitors
GROUP BY competitor_id
HAVING COUNT(*) > 1;
GO

-- ---------------------------------------------------------------------
-- 3. Foreign key: every ranking points to an existing competitor
-- ---------------------------------------------------------------------
SELECT r.rank_id, r.competitor_id
FROM dbo.competitor_rankings AS r
LEFT JOIN dbo.competitors AS c
       ON c.competitor_id = r.competitor_id
WHERE c.competitor_id IS NULL;
GO

-- ---------------------------------------------------------------------
-- 4. One ranking row per competitor (no repeated snapshot rows)
-- ---------------------------------------------------------------------
SELECT competitor_id, COUNT(*) AS ranking_rows
FROM dbo.competitor_rankings
GROUP BY competitor_id
HAVING COUNT(*) > 1;
GO

-- ---------------------------------------------------------------------
-- 5. Column constraints: NULLs in NOT NULL columns
-- ---------------------------------------------------------------------
SELECT
    SUM(CASE WHEN name IS NULL OR LTRIM(RTRIM(name)) = '' THEN 1 ELSE 0 END)                    AS bad_names,
    SUM(CASE WHEN country IS NULL OR LTRIM(RTRIM(country)) = '' THEN 1 ELSE 0 END)              AS bad_countries,
    SUM(CASE WHEN country_code IS NULL OR LEN(LTRIM(RTRIM(country_code))) <> 3 THEN 1 ELSE 0 END) AS bad_country_codes,
    SUM(CASE WHEN abbreviation IS NULL OR LTRIM(RTRIM(abbreviation)) = '' THEN 1 ELSE 0 END)    AS bad_abbreviations
FROM dbo.competitors;
GO

SELECT
    SUM(CASE WHEN rank IS NULL THEN 1 ELSE 0 END)                AS missing_rank,
    SUM(CASE WHEN movement IS NULL THEN 1 ELSE 0 END)            AS missing_movement,
    SUM(CASE WHEN points IS NULL THEN 1 ELSE 0 END)              AS missing_points,
    SUM(CASE WHEN competitions_played IS NULL THEN 1 ELSE 0 END) AS missing_competitions
FROM dbo.competitor_rankings;
GO

-- ---------------------------------------------------------------------
-- 6. Value ranges (the feed covers ranks 1-500, points >= 0)
-- ---------------------------------------------------------------------
SELECT rank_id, rank, points
FROM dbo.competitor_rankings
WHERE rank < 1 OR rank > 500;
GO

SELECT rank_id, competitor_id, points
FROM dbo.competitor_rankings
WHERE points < 0;
GO

SELECT rank_id, competitor_id, movement
FROM dbo.competitor_rankings
WHERE movement < -500 OR movement > 500;
GO

-- ---------------------------------------------------------------------
-- 7. Leader sanity check: rank 1 players must hold the maximum points
-- ---------------------------------------------------------------------
SELECT MAX(points) AS max_points,
       (SELECT MAX(points) FROM dbo.competitor_rankings WHERE rank = 1) AS rank1_points
FROM dbo.competitor_rankings;
GO

-- ---------------------------------------------------------------------
-- 8. Ties: doubles partners share rank and points
-- ---------------------------------------------------------------------
SELECT rank, points, COUNT(*) AS players
FROM dbo.competitor_rankings
GROUP BY rank, points
HAVING COUNT(*) > 1
ORDER BY rank;
GO

-- ---------------------------------------------------------------------
-- 9. Country code format (ISO alpha-3; UNK / NEU are placeholders)
-- ---------------------------------------------------------------------
SELECT DISTINCT country_code
FROM dbo.competitors
WHERE country_code NOT LIKE '[A-Z][A-Z][A-Z]';
GO

-- ---------------------------------------------------------------------
-- 10. Movement distribution (should add up to the ranking row count)
-- ---------------------------------------------------------------------
SELECT SUM(CASE WHEN movement > 0 THEN 1 ELSE 0 END) AS moved_up,
       SUM(CASE WHEN movement = 0 THEN 1 ELSE 0 END) AS unchanged,
       SUM(CASE WHEN movement < 0 THEN 1 ELSE 0 END) AS moved_down,
       COUNT(*)                                      AS total
FROM dbo.competitor_rankings;
GO
