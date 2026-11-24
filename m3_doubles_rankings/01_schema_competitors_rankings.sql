-- ============================================================
-- 01_schema_competitors_rankings.sql
-- M3 - Doubles rankings: Competitors + Competitor_Rankings
-- Primary dialect: SQL Server / SSMS (same database as M2)
-- A MySQL / PostgreSQL version is at the bottom of this file.
-- ============================================================

USE tennis_db;
GO

-- Drop in FK order so the script can be re-run safely
IF OBJECT_ID('dbo.competitor_rankings', 'U') IS NOT NULL
    DROP TABLE dbo.competitor_rankings;
IF OBJECT_ID('dbo.competitors', 'U') IS NOT NULL
    DROP TABLE dbo.competitors;
GO

-- ------------------------------------------------------------
-- Competitors: one row per doubles player (or doubles team)
-- ------------------------------------------------------------
CREATE TABLE dbo.competitors (
    competitor_id VARCHAR(50)   NOT NULL,
    name          NVARCHAR(100) NOT NULL,
    country       NVARCHAR(100) NOT NULL,
    country_code  CHAR(3)       NOT NULL,
    abbreviation  VARCHAR(10)   NOT NULL,
    CONSTRAINT pk_competitors PRIMARY KEY (competitor_id)
);
GO

-- ------------------------------------------------------------
-- Competitor_Rankings: one row per ranked competitor per snapshot
-- rank_id is a surrogate key because doubles partners share a rank
-- (e.g. two players can both be world number 1), so rank alone
-- cannot identify a row.
-- ------------------------------------------------------------
CREATE TABLE dbo.competitor_rankings (
    rank_id             INT          IDENTITY(1, 1) NOT NULL,
    rank                INT          NOT NULL,
    movement            INT          NOT NULL,
    points              INT          NOT NULL,
    competitions_played INT          NOT NULL,
    competitor_id       VARCHAR(50)  NOT NULL,
    CONSTRAINT pk_competitor_rankings PRIMARY KEY (rank_id),
    CONSTRAINT fk_rankings_competitor
        FOREIGN KEY (competitor_id) REFERENCES dbo.competitors (competitor_id)
);
GO

-- Indexes for the analysis queries and the Streamlit filters
CREATE INDEX idx_rankings_rank        ON dbo.competitor_rankings (rank);
CREATE INDEX idx_rankings_points      ON dbo.competitor_rankings (points DESC);
CREATE INDEX idx_rankings_competitor  ON dbo.competitor_rankings (competitor_id);
CREATE INDEX idx_rankings_movement    ON dbo.competitor_rankings (movement);
CREATE INDEX idx_competitors_country  ON dbo.competitors (country);
CREATE INDEX idx_competitors_code     ON dbo.competitors (country_code);
GO


-- ============================================================
-- MySQL 8 / PostgreSQL version
-- ------------------------------------------------------------
-- MySQL: `rank` is a reserved word, so it must be back-quoted.
-- PostgreSQL: `rank` is a reserved word too, use "rank".
--
-- CREATE TABLE competitors (
--     competitor_id VARCHAR(50)  NOT NULL PRIMARY KEY,
--     name          VARCHAR(100) NOT NULL,
--     country       VARCHAR(100) NOT NULL,
--     country_code  CHAR(3)      NOT NULL,
--     abbreviation  VARCHAR(10)  NOT NULL
-- );
--
-- CREATE TABLE competitor_rankings (
--     rank_id             INT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
--     `rank`              INT          NOT NULL,
--     movement            INT          NOT NULL,
--     points              INT          NOT NULL,
--     competitions_played INT          NOT NULL,
--     competitor_id       VARCHAR(50)  NOT NULL,
--     CONSTRAINT fk_rankings_competitor
--         FOREIGN KEY (competitor_id) REFERENCES competitors (competitor_id)
-- );
--
-- CREATE INDEX idx_rankings_rank   ON competitor_rankings (`rank`);
-- CREATE INDEX idx_rankings_points ON competitor_rankings (points);
-- ============================================================
