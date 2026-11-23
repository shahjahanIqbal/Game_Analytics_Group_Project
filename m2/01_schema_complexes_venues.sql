-- ============================================================
-- 01_schema_complexes_venues.sql
-- Creates the complexes and venues tables (SQL Server / SSMS)
-- ============================================================

USE tennis_db;
GO

-- Drop old tables first (venues before complexes, because of the foreign key)
DROP TABLE IF EXISTS venues;
DROP TABLE IF EXISTS complexes;
GO

-- 1) Complexes table
CREATE TABLE complexes (
    complex_id   VARCHAR(50)   NOT NULL PRIMARY KEY,
    complex_name NVARCHAR(100) NOT NULL
);

-- 2) Venues table
CREATE TABLE venues (
    venue_id     VARCHAR(50)   NOT NULL PRIMARY KEY,
    venue_name   NVARCHAR(100) NOT NULL,
    city_name    NVARCHAR(100) NOT NULL,
    country_name NVARCHAR(100) NOT NULL,
    country_code CHAR(3)       NOT NULL,
    timezone     VARCHAR(100)  NOT NULL,
    complex_id   VARCHAR(50)   NULL,
    FOREIGN KEY (complex_id) REFERENCES complexes(complex_id)
);

CREATE INDEX idx_venues_complex ON venues(complex_id);
CREATE INDEX idx_venues_country ON venues(country_name);
GO
