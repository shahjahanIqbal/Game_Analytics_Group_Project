-- ============================================================
-- 03_queries_competitors_rankings.sql
-- M3 - Doubles rankings analysis queries (SQL Server / SSMS)
--
-- The six required queries are Q1-Q6. Q7-Q10 are extra insights
-- used by the Streamlit dashboard (M5).
-- ============================================================

USE tennis_db;
GO

-- ---------------------------------------------------------------------
-- Q1. Get all competitors with their rank and points
-- ---------------------------------------------------------------------
SELECT c.competitor_id,
       c.name,
       c.country,
       c.country_code,
       c.abbreviation,
       r.rank,
       r.movement,
       r.points,
       r.competitions_played
FROM dbo.competitors AS c
INNER JOIN dbo.competitor_rankings AS r
        ON r.competitor_id = c.competitor_id
ORDER BY r.rank ASC, r.points DESC, c.name ASC;
GO

-- ---------------------------------------------------------------------
-- Q2. Find competitors ranked in the top 5
-- Note: doubles partners share a rank, and a shared rank skips the next
-- number (two players at 3 means no rank 4), so this returns about five
-- players per tour - ten rows for ATP + WTA. Correct, not duplicates.
-- ---------------------------------------------------------------------
SELECT c.name,
       c.country,
       r.rank,
       r.points,
       r.movement
FROM dbo.competitors AS c
INNER JOIN dbo.competitor_rankings AS r
        ON r.competitor_id = c.competitor_id
WHERE r.rank <= 5
ORDER BY r.rank ASC, r.points DESC, c.name ASC;
GO

-- ---------------------------------------------------------------------
-- Q3. List competitors with no rank movement (stable rank)
-- ---------------------------------------------------------------------
SELECT c.name,
       c.country,
       r.rank,
       r.points,
       r.movement
FROM dbo.competitors AS c
INNER JOIN dbo.competitor_rankings AS r
        ON r.competitor_id = c.competitor_id
WHERE r.movement = 0
ORDER BY r.rank ASC, r.points DESC;
GO

-- ---------------------------------------------------------------------
-- Q4. Get the total points of competitors from a specific country
--     (example: Croatia)
-- ---------------------------------------------------------------------
-- 4a. One total for the country
SELECT c.country,
       COUNT(*)          AS competitors,
       SUM(r.points)     AS total_points,
       AVG(r.points * 1.0) AS average_points
FROM dbo.competitors AS c
INNER JOIN dbo.competitor_rankings AS r
        ON r.competitor_id = c.competitor_id
WHERE c.country = 'Croatia'
GROUP BY c.country;
GO

-- 4b. The individual Croatian competitors behind that total
SELECT c.name,
       r.rank,
       r.points,
       r.movement,
       r.competitions_played
FROM dbo.competitors AS c
INNER JOIN dbo.competitor_rankings AS r
        ON r.competitor_id = c.competitor_id
WHERE c.country = 'Croatia'
ORDER BY r.points DESC;
GO

-- ---------------------------------------------------------------------
-- Q5. Count the number of competitors per country
-- ---------------------------------------------------------------------
SELECT c.country,
       c.country_code,
       COUNT(*)                                       AS total_competitors,
       SUM(r.points)                                  AS total_points,
       CAST(AVG(r.points * 1.0) AS DECIMAL(10, 2))    AS average_points,
       MIN(r.rank)                                    AS best_rank
FROM dbo.competitors AS c
INNER JOIN dbo.competitor_rankings AS r
        ON r.competitor_id = c.competitor_id
GROUP BY c.country, c.country_code
ORDER BY total_competitors DESC, total_points DESC;
GO

-- ---------------------------------------------------------------------
-- Q6. Find competitors with the highest points in the current week
--     The table holds one weekly snapshot, so "current week" is the
--     data that was loaded by 02_import_competitors_rankings.sql.
--     ATP and WTA points are separate scales; without a tour column the
--     leaderboard mixes both, so read it as "best points in the snapshot".
-- ---------------------------------------------------------------------
-- 6a. Leaderboard (top 10 by points)
SELECT TOP (10)
       c.name,
       c.country,
       r.rank,
       r.points,
       r.competitions_played
FROM dbo.competitors AS c
INNER JOIN dbo.competitor_rankings AS r
        ON r.competitor_id = c.competitor_id
ORDER BY r.points DESC, c.name ASC;
GO

-- 6b. Only the player(s) on the maximum points (ties included)
SELECT c.name,
       c.country,
       r.rank,
       r.points
FROM dbo.competitors AS c
INNER JOIN dbo.competitor_rankings AS r
        ON r.competitor_id = c.competitor_id
WHERE r.points = (SELECT MAX(points) FROM dbo.competitor_rankings)
ORDER BY c.name;
GO

-- ---------------------------------------------------------------------
-- Q7. Points-based world ranking with a window function
--     Shows the difference between the official rank and the points
--     order, and the gap to the leader.
-- ---------------------------------------------------------------------
SELECT c.name,
       c.country,
       r.rank                                   AS official_rank,
       DENSE_RANK() OVER (ORDER BY r.points DESC) AS points_rank,
       r.points,
       MAX(r.points) OVER () - r.points          AS points_behind_leader,
       CAST(100.0 * r.points
            / NULLIF(MAX(r.points) OVER (), 0) AS DECIMAL(5, 2)) AS pct_of_leader
FROM dbo.competitors AS c
INNER JOIN dbo.competitor_rankings AS r
        ON r.competitor_id = c.competitor_id
ORDER BY r.points DESC, c.name;
GO

-- ---------------------------------------------------------------------
-- Q8. Biggest movers: risers and fallers compared with last week
--     movement > 0 = moved up, movement < 0 = moved down
-- ---------------------------------------------------------------------
SELECT TOP (10)
       c.name,
       c.country,
       r.rank,
       r.movement,
       r.points
FROM dbo.competitors AS c
INNER JOIN dbo.competitor_rankings AS r
        ON r.competitor_id = c.competitor_id
WHERE r.movement <> 0
ORDER BY r.movement DESC, r.rank ASC;
GO

SELECT TOP (10)
       c.name,
       c.country,
       r.rank,
       r.movement,
       r.points
FROM dbo.competitors AS c
INNER JOIN dbo.competitor_rankings AS r
        ON r.competitor_id = c.competitor_id
WHERE r.movement <> 0
ORDER BY r.movement ASC, r.rank ASC;
GO

-- ---------------------------------------------------------------------
-- Q9. Doubles teams: players who share a rank and the same points
--     (SQL Server 2017+; MySQL: GROUP_CONCAT(c.name ORDER BY c.name))
-- ---------------------------------------------------------------------
SELECT r.rank,
       r.points,
       COUNT(*)                                  AS players,
       STRING_AGG(c.name, ' / ')                 AS team
FROM dbo.competitors AS c
INNER JOIN dbo.competitor_rankings AS r
        ON r.competitor_id = c.competitor_id
GROUP BY r.rank, r.points
HAVING COUNT(*) > 1
ORDER BY r.rank ASC;
GO

-- ---------------------------------------------------------------------
-- Q10. Country strength: country totals ranked against each other
--      (useful for the country-wise dashboard page)
-- ---------------------------------------------------------------------
SELECT c.country,
       COUNT(*)              AS competitors,
       SUM(r.points)         AS total_points,
       CAST(AVG(r.points * 1.0) AS DECIMAL(10, 2)) AS average_points,
       MIN(r.rank)           AS best_rank,
       RANK() OVER (ORDER BY SUM(r.points) DESC)   AS country_points_rank
FROM dbo.competitors AS c
INNER JOIN dbo.competitor_rankings AS r
        ON r.competitor_id = c.competitor_id
GROUP BY c.country
ORDER BY total_points DESC;
GO
