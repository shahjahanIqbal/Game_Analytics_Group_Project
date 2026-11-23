-- =====================================================================
-- M1 - Competitions: schema (for M4 reference) and analysis queries
-- Dialect: MySQL (also valid on PostgreSQL unless noted)
-- =====================================================================

-- ---------------------------------------------------------------------
-- Schema (matches the project specification)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Categories (
    category_id   VARCHAR(50)  PRIMARY KEY,
    category_name VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS Competitions (
    competition_id   VARCHAR(50)  PRIMARY KEY,
    competition_name VARCHAR(100) NOT NULL,
    parent_id        VARCHAR(50)  NULL,
    type             VARCHAR(20)  NOT NULL,
    gender           VARCHAR(10)  NOT NULL,
    category_id      VARCHAR(50),
    FOREIGN KEY (category_id) REFERENCES Categories(category_id)
);

-- Indexes to speed up the queries below
CREATE INDEX idx_comp_category ON Competitions(category_id);
CREATE INDEX idx_comp_parent   ON Competitions(parent_id);
CREATE INDEX idx_comp_type     ON Competitions(type);

-- ---------------------------------------------------------------------
-- Q1. List all competitions along with their category name
-- ---------------------------------------------------------------------
SELECT c.competition_id,
       c.competition_name,
       c.type,
       c.gender,
       cat.category_name
FROM Competitions c
LEFT JOIN Categories cat ON c.category_id = cat.category_id
ORDER BY cat.category_name, c.competition_name;

-- ---------------------------------------------------------------------
-- Q2. Count the number of competitions in each category
-- ---------------------------------------------------------------------
SELECT cat.category_id,
       cat.category_name,
       COUNT(c.competition_id) AS total_competitions
FROM Categories cat
LEFT JOIN Competitions c ON c.category_id = cat.category_id
GROUP BY cat.category_id, cat.category_name
ORDER BY total_competitions DESC;

-- ---------------------------------------------------------------------
-- Q3. Find all competitions of type 'doubles'
-- ---------------------------------------------------------------------
SELECT competition_id, competition_name, gender, category_id
FROM Competitions
WHERE type = 'doubles'
ORDER BY competition_name;

-- ---------------------------------------------------------------------
-- Q4. Get competitions that belong to a specific category (e.g., ITF Men)
-- ---------------------------------------------------------------------
SELECT c.competition_id,
       c.competition_name,
       c.type,
       c.gender
FROM Competitions c
JOIN Categories cat ON c.category_id = cat.category_id
WHERE cat.category_name = 'ITF Men'
ORDER BY c.competition_name;

-- ---------------------------------------------------------------------
-- Q5. Identify parent competitions and their sub-competitions
-- ---------------------------------------------------------------------
SELECT p.competition_id   AS parent_competition_id,
       p.competition_name AS parent_competition_name,
       s.competition_id   AS sub_competition_id,
       s.competition_name AS sub_competition_name,
       s.type             AS sub_type,
       s.gender           AS sub_gender
FROM Competitions s
JOIN Competitions p ON s.parent_id = p.competition_id
ORDER BY p.competition_name, s.competition_name;

-- ---------------------------------------------------------------------
-- Q6. Analyze the distribution of competition types by category
-- ---------------------------------------------------------------------
SELECT cat.category_name,
       c.type,
       COUNT(*) AS total_competitions
FROM Competitions c
JOIN Categories cat ON c.category_id = cat.category_id
GROUP BY cat.category_name, c.type
ORDER BY cat.category_name, total_competitions DESC;

-- ---------------------------------------------------------------------
-- Q7. List all competitions with no parent (top-level competitions)
-- ---------------------------------------------------------------------
SELECT competition_id, competition_name, type, gender, category_id
FROM Competitions
WHERE parent_id IS NULL
ORDER BY competition_name;

-- ---------------------------------------------------------------------
-- Bonus: validation checks M4 can run after loading
-- ---------------------------------------------------------------------
-- Competitions whose category does not exist (should return 0 rows)
SELECT c.competition_id
FROM Competitions c
LEFT JOIN Categories cat ON c.category_id = cat.category_id
WHERE c.category_id IS NOT NULL AND cat.category_id IS NULL;

-- Parent IDs that point to competitions not in the table
-- (can occur because the API returns a partial hierarchy)
SELECT DISTINCT c.parent_id
FROM Competitions c
LEFT JOIN Competitions p ON c.parent_id = p.competition_id
WHERE c.parent_id IS NOT NULL AND p.competition_id IS NULL;

-- Row counts
SELECT (SELECT COUNT(*) FROM Categories)   AS categories,
       (SELECT COUNT(*) FROM Competitions) AS competitions;
