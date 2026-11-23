-- ============================================================
-- 02_import_complexes_venues.sql
-- Loads the CSV files into the tables (SQL Server / SSMS)
-- Copy complexes.csv and venues.csv to C:\temp\ first.
-- Run complexes first, then venues (foreign key).
-- ============================================================

USE tennis_db;
GO

BULK INSERT complexes
FROM 'C:\temp\complexes.csv'
WITH (
    FORMAT = 'CSV',
    FIRSTROW = 2,
    FIELDQUOTE = '"',
    CODEPAGE = '65001'
);
GO

BULK INSERT venues
FROM 'C:\temp\venues.csv'
WITH (
    FORMAT = 'CSV',
    FIRSTROW = 2,
    FIELDQUOTE = '"',
    CODEPAGE = '65001'
);
GO
