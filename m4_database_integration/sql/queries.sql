USE tennis_db;
GO
/* ---------------- M1: Categories and competitions Q1-Q7 ---------------- */
-- M1 Q1
SELECT c.competition_id,c.competition_name,c.[type],c.gender,cat.category_name
FROM dbo.competitions c LEFT JOIN dbo.categories cat ON c.category_id=cat.category_id
ORDER BY cat.category_name,c.competition_name;
GO
-- M1 Q2
SELECT cat.category_id,cat.category_name,COUNT(c.competition_id) AS total_competitions
FROM dbo.categories cat LEFT JOIN dbo.competitions c ON c.category_id=cat.category_id
GROUP BY cat.category_id,cat.category_name ORDER BY total_competitions DESC;
GO
-- M1 Q3
SELECT competition_id,competition_name,gender,category_id FROM dbo.competitions
WHERE [type]='doubles' ORDER BY competition_name;
GO
-- M1 Q4
SELECT c.competition_id,c.competition_name,c.[type],c.gender
FROM dbo.competitions c JOIN dbo.categories cat ON c.category_id=cat.category_id
WHERE cat.category_name='ITF Men' ORDER BY c.competition_name;
GO
-- M1 Q5
SELECT p.competition_id AS parent_competition_id,p.competition_name AS parent_competition_name,
s.competition_id AS sub_competition_id,s.competition_name AS sub_competition_name,
s.[type] AS sub_type,s.gender AS sub_gender
FROM dbo.competitions s JOIN dbo.competitions p ON s.parent_id=p.competition_id
ORDER BY p.competition_name,s.competition_name;
GO
-- M1 Q6
SELECT cat.category_name,c.[type],COUNT(*) AS total_competitions
FROM dbo.competitions c JOIN dbo.categories cat ON c.category_id=cat.category_id
GROUP BY cat.category_name,c.[type] ORDER BY cat.category_name,total_competitions DESC;
GO
-- M1 Q7
SELECT competition_id,competition_name,[type],gender,category_id
FROM dbo.competitions WHERE parent_id IS NULL ORDER BY competition_name;
GO

/* ---------------- M2: Complexes and venues Q2.1-Q2.7 ---------------- */
-- M2 Q2.1
SELECT v.venue_id,v.venue_name,v.city_name,v.country_name,cx.complex_name
FROM dbo.venues v LEFT JOIN dbo.complexes cx ON cx.complex_id=v.complex_id
ORDER BY cx.complex_name,v.venue_name;
GO
-- M2 Q2.2
SELECT cx.complex_name,COUNT(v.venue_id) AS total_venues
FROM dbo.complexes cx LEFT JOIN dbo.venues v ON v.complex_id=cx.complex_id
GROUP BY cx.complex_id,cx.complex_name ORDER BY total_venues DESC,cx.complex_name;
GO
-- M2 Q2.3
SELECT venue_id,venue_name,city_name,country_name,country_code,timezone,complex_id
FROM dbo.venues WHERE country_name='Chile' ORDER BY city_name,venue_name;
GO
-- M2 Q2.4
SELECT venue_name,city_name,country_name,timezone FROM dbo.venues
ORDER BY timezone,venue_name;
GO
-- M2 Q2.5
SELECT cx.complex_name,COUNT(v.venue_id) AS total_venues
FROM dbo.complexes cx JOIN dbo.venues v ON v.complex_id=cx.complex_id
GROUP BY cx.complex_id,cx.complex_name HAVING COUNT(v.venue_id)>1
ORDER BY total_venues DESC,cx.complex_name;
GO
-- M2 Q2.6
SELECT country_name,COUNT(*) AS total_venues FROM dbo.venues
GROUP BY country_name ORDER BY total_venues DESC,country_name;
GO
-- M2 Q2.6b
SELECT country_name,venue_name,city_name FROM dbo.venues ORDER BY country_name,venue_name;
GO
-- M2 Q2.7
SELECT v.venue_id,v.venue_name,v.city_name,v.country_name,v.timezone
FROM dbo.venues v JOIN dbo.complexes cx ON cx.complex_id=v.complex_id
WHERE cx.complex_name='Nacional' ORDER BY v.venue_name;
GO

/* ---------------- M3: Doubles competitors and rankings Q1-Q10 ---------------- */
-- M3 Q1
SELECT c.competitor_id,c.name,c.country,c.country_code,c.abbreviation,
r.[rank],r.movement,r.points,r.competitions_played
FROM dbo.competitors c JOIN dbo.competitor_rankings r ON r.competitor_id=c.competitor_id
ORDER BY r.[rank],r.points DESC,c.name;
GO
-- M3 Q2
SELECT c.name,c.country,r.[rank],r.points,r.movement
FROM dbo.competitors c JOIN dbo.competitor_rankings r ON r.competitor_id=c.competitor_id
WHERE r.[rank]<=5 ORDER BY r.[rank],r.points DESC,c.name;
GO
-- M3 Q3
SELECT c.name,c.country,r.[rank],r.points,r.movement
FROM dbo.competitors c JOIN dbo.competitor_rankings r ON r.competitor_id=c.competitor_id
WHERE r.movement=0 ORDER BY r.[rank],r.points DESC;
GO
-- M3 Q4a
SELECT c.country,COUNT(*) AS competitors,SUM(r.points) AS total_points,
AVG(CAST(r.points AS DECIMAL(12,2))) AS average_points
FROM dbo.competitors c JOIN dbo.competitor_rankings r ON r.competitor_id=c.competitor_id
WHERE c.country='Croatia' GROUP BY c.country;
GO
-- M3 Q4b
SELECT c.name,r.[rank],r.points,r.movement,r.competitions_played
FROM dbo.competitors c JOIN dbo.competitor_rankings r ON r.competitor_id=c.competitor_id
WHERE c.country='Croatia' ORDER BY r.points DESC;
GO
-- M3 Q5
SELECT c.country,c.country_code,COUNT(*) AS total_competitors,SUM(r.points) AS total_points,
CAST(AVG(CAST(r.points AS DECIMAL(12,2))) AS DECIMAL(10,2)) AS average_points,
MIN(r.[rank]) AS best_rank
FROM dbo.competitors c JOIN dbo.competitor_rankings r ON r.competitor_id=c.competitor_id
GROUP BY c.country,c.country_code ORDER BY total_competitors DESC,total_points DESC;
GO
-- M3 Q6a
SELECT TOP (10) c.name,c.country,r.[rank],r.points,r.competitions_played
FROM dbo.competitors c JOIN dbo.competitor_rankings r ON r.competitor_id=c.competitor_id
ORDER BY r.points DESC,c.name;
GO
-- M3 Q6b
SELECT c.name,c.country,r.[rank],r.points
FROM dbo.competitors c JOIN dbo.competitor_rankings r ON r.competitor_id=c.competitor_id
WHERE r.points=(SELECT MAX(points) FROM dbo.competitor_rankings) ORDER BY c.name;
GO
-- M3 Q7
SELECT c.name,c.country,r.[rank] AS official_rank,
DENSE_RANK() OVER(ORDER BY r.points DESC) AS points_rank,r.points,
MAX(r.points) OVER()-r.points AS points_behind_leader,
CAST(100.0*r.points/NULLIF(MAX(r.points) OVER(),0) AS DECIMAL(5,2)) AS pct_of_leader
FROM dbo.competitors c JOIN dbo.competitor_rankings r ON r.competitor_id=c.competitor_id
ORDER BY r.points DESC,c.name;
GO
-- M3 Q8a risers
SELECT TOP (10) c.name,c.country,r.[rank],r.movement,r.points
FROM dbo.competitors c JOIN dbo.competitor_rankings r ON r.competitor_id=c.competitor_id
WHERE r.movement>0 ORDER BY r.movement DESC,r.[rank];
GO
-- M3 Q8b fallers
SELECT TOP (10) c.name,c.country,r.[rank],r.movement,r.points
FROM dbo.competitors c JOIN dbo.competitor_rankings r ON r.competitor_id=c.competitor_id
WHERE r.movement<0 ORDER BY r.movement ASC,r.[rank];
GO
-- M3 Q9 doubles partner groups; tied rank + points are intentional.
SELECT r.[rank],r.points,COUNT(*) AS players,
STRING_AGG(CAST(c.name AS NVARCHAR(MAX)),N' / ') AS team
FROM dbo.competitors c JOIN dbo.competitor_rankings r ON r.competitor_id=c.competitor_id
GROUP BY r.[rank],r.points HAVING COUNT(*)>1 ORDER BY r.[rank];
GO
-- M3 Q10 country strength
SELECT c.country,COUNT(*) AS competitors,SUM(r.points) AS total_points,
CAST(AVG(CAST(r.points AS DECIMAL(12,2))) AS DECIMAL(10,2)) AS average_points,
MIN(r.[rank]) AS best_rank,RANK() OVER(ORDER BY SUM(r.points) DESC) AS country_points_rank
FROM dbo.competitors c JOIN dbo.competitor_rankings r ON r.competitor_id=c.competitor_id
GROUP BY c.country ORDER BY total_points DESC;
GO
