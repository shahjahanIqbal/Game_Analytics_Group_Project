-- ============================================================
-- 03_queries_complexes_venues.sql
-- Complexes and venues queries (standard SQL, runs in SSMS)
-- ============================================================

USE tennis_db;
GO

-- 2.1 List all venues along with their associated complex name
SELECT v.venue_id,
       v.venue_name,
       v.city_name,
       v.country_name,
       cx.complex_name
FROM venues v
LEFT JOIN complexes cx ON cx.complex_id = v.complex_id
ORDER BY cx.complex_name, v.venue_name;

-- 2.2 Count the number of venues in each complex
SELECT cx.complex_name,
       COUNT(v.venue_id) AS total_venues
FROM complexes cx
LEFT JOIN venues v ON v.complex_id = cx.complex_id
GROUP BY cx.complex_id, cx.complex_name
ORDER BY total_venues DESC, cx.complex_name;

-- 2.3 Get details of venues in a specific country (e.g., Chile)
SELECT venue_id, venue_name, city_name, country_name, country_code, timezone, complex_id
FROM venues
WHERE country_name = 'Chile'
ORDER BY city_name, venue_name;

-- 2.4 Identify all venues and their timezones
SELECT venue_name, city_name, country_name, timezone
FROM venues
ORDER BY timezone, venue_name;

-- 2.5 Find complexes that have more than one venue
SELECT cx.complex_name,
       COUNT(v.venue_id) AS total_venues
FROM complexes cx
JOIN venues v ON v.complex_id = cx.complex_id
GROUP BY cx.complex_id, cx.complex_name
HAVING COUNT(v.venue_id) > 1
ORDER BY total_venues DESC, cx.complex_name;

-- 2.6 List venues grouped by country (number of venues in each country)
SELECT country_name,
       COUNT(*) AS total_venues
FROM venues
GROUP BY country_name
ORDER BY total_venues DESC, country_name;

-- 2.6b List every venue, grouped (sorted) by country
SELECT country_name,
       venue_name,
       city_name
FROM venues
ORDER BY country_name, venue_name;

-- 2.7 Find all venues for a specific complex (e.g., Nacional)
SELECT v.venue_id, v.venue_name, v.city_name, v.country_name, v.timezone
FROM venues v
JOIN complexes cx ON cx.complex_id = v.complex_id
WHERE cx.complex_name = 'Nacional'
ORDER BY v.venue_name;
