-- ============================================================
-- 04_checks_complexes_venues.sql
-- Post-import checks (SQL Server / SSMS)
-- ============================================================

USE tennis_db;
GO

-- 1. Row counts (expect complexes = 787, venues = 4181)
SELECT 'complexes' AS table_name, COUNT(*) AS total_rows FROM complexes
UNION ALL
SELECT 'venues', COUNT(*) FROM venues;

-- 2. Orphan venues: venues whose complex_id is not in complexes (expect 0)
SELECT COUNT(*) AS orphan_venues
FROM venues v
LEFT JOIN complexes c ON c.complex_id = v.complex_id
WHERE v.complex_id IS NOT NULL AND c.complex_id IS NULL;

-- 3. Preview a few rows
SELECT TOP 10 * FROM complexes;
SELECT TOP 10 * FROM venues;
