USE tennis_db;
GO
-- Expected snapshot counts: categories 18, competitions 6743, complexes 787,
-- venues 4181, competitors 1000, competitor_rankings 1000.
SELECT 'categories' AS table_name,COUNT(*) AS total_rows FROM dbo.categories
UNION ALL SELECT 'competitions',COUNT(*) FROM dbo.competitions
UNION ALL SELECT 'complexes',COUNT(*) FROM dbo.complexes
UNION ALL SELECT 'venues',COUNT(*) FROM dbo.venues
UNION ALL SELECT 'competitors',COUNT(*) FROM dbo.competitors
UNION ALL SELECT 'competitor_rankings',COUNT(*) FROM dbo.competitor_rankings;
GO
-- Orphan checks: each count should be zero.
SELECT COUNT(*) AS bad_competition_categories FROM dbo.competitions c
LEFT JOIN dbo.categories cat ON cat.category_id=c.category_id
WHERE c.category_id IS NOT NULL AND cat.category_id IS NULL;
SELECT COUNT(*) AS bad_competition_parents FROM dbo.competitions c
LEFT JOIN dbo.competitions p ON p.competition_id=c.parent_id
WHERE c.parent_id IS NOT NULL AND p.competition_id IS NULL;
SELECT COUNT(*) AS bad_venue_complexes FROM dbo.venues v
LEFT JOIN dbo.complexes x ON x.complex_id=v.complex_id
WHERE v.complex_id IS NOT NULL AND x.complex_id IS NULL;
SELECT COUNT(*) AS bad_ranking_competitors FROM dbo.competitor_rankings r
LEFT JOIN dbo.competitors c ON c.competitor_id=r.competitor_id
WHERE c.competitor_id IS NULL;
GO
-- Duplicate primary keys should return no rows.
SELECT category_id,COUNT(*) n FROM dbo.categories GROUP BY category_id HAVING COUNT(*)>1;
SELECT competition_id,COUNT(*) n FROM dbo.competitions GROUP BY competition_id HAVING COUNT(*)>1;
SELECT complex_id,COUNT(*) n FROM dbo.complexes GROUP BY complex_id HAVING COUNT(*)>1;
SELECT venue_id,COUNT(*) n FROM dbo.venues GROUP BY venue_id HAVING COUNT(*)>1;
SELECT competitor_id,COUNT(*) n FROM dbo.competitors GROUP BY competitor_id HAVING COUNT(*)>1;
GO
-- Current snapshot: one ranking row per competitor.
SELECT competitor_id,COUNT(*) n FROM dbo.competitor_rankings
GROUP BY competitor_id HAVING COUNT(*)>1;
-- Rank ties are valid for doubles partners; this is an informational report.
SELECT [rank],points,COUNT(*) AS tied_competitors FROM dbo.competitor_rankings
GROUP BY [rank],points HAVING COUNT(*)>1 ORDER BY [rank];
-- Invalid values should return zero.
SELECT COUNT(*) AS invalid_rank_values FROM dbo.competitor_rankings
WHERE [rank]<1 OR [rank]>500 OR points<0 OR competitions_played<0;
SELECT COUNT(*) AS invalid_country_codes FROM dbo.competitors
WHERE country_code IS NULL OR LEN(LTRIM(RTRIM(country_code)))<>3;
GO
