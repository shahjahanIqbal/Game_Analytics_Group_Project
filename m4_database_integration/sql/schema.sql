IF DB_ID(N'tennis_db') IS NULL CREATE DATABASE tennis_db;
GO
USE tennis_db;
GO
IF OBJECT_ID(N'dbo.categories', N'U') IS NULL
CREATE TABLE dbo.categories (
 category_id VARCHAR(50) NOT NULL PRIMARY KEY,
 category_name NVARCHAR(100) NOT NULL
);
GO
IF OBJECT_ID(N'dbo.competitions', N'U') IS NULL
CREATE TABLE dbo.competitions (
 competition_id VARCHAR(50) NOT NULL PRIMARY KEY,
 competition_name NVARCHAR(100) NOT NULL,
 parent_id VARCHAR(50) NULL,
 [type] VARCHAR(20) NOT NULL,
 gender VARCHAR(10) NOT NULL,
 category_id VARCHAR(50) NULL,
 CONSTRAINT fk_competitions_category FOREIGN KEY(category_id) REFERENCES dbo.categories(category_id),
 CONSTRAINT fk_competitions_parent FOREIGN KEY(parent_id) REFERENCES dbo.competitions(competition_id)
);
GO
/* Add the self-reference when M1's earlier schema has already created
   competitions without this optional hierarchy constraint. */
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name=N'fk_competitions_parent')
    ALTER TABLE dbo.competitions
    ADD CONSTRAINT fk_competitions_parent
    FOREIGN KEY(parent_id) REFERENCES dbo.competitions(competition_id);
GO
IF OBJECT_ID(N'dbo.complexes', N'U') IS NULL
CREATE TABLE dbo.complexes (
 complex_id VARCHAR(50) NOT NULL PRIMARY KEY,
 complex_name NVARCHAR(100) NOT NULL
);
GO
IF OBJECT_ID(N'dbo.venues', N'U') IS NULL
CREATE TABLE dbo.venues (
 venue_id VARCHAR(50) NOT NULL PRIMARY KEY,
 venue_name NVARCHAR(100) NOT NULL,
 city_name NVARCHAR(100) NOT NULL,
 country_name NVARCHAR(100) NOT NULL,
 country_code CHAR(3) NOT NULL,
 timezone VARCHAR(100) NOT NULL,
 complex_id VARCHAR(50) NULL,
 CONSTRAINT fk_venues_complex FOREIGN KEY(complex_id) REFERENCES dbo.complexes(complex_id)
);
GO
IF OBJECT_ID(N'dbo.competitors', N'U') IS NULL
CREATE TABLE dbo.competitors (
 competitor_id VARCHAR(50) NOT NULL PRIMARY KEY,
 name NVARCHAR(100) NOT NULL,
 country NVARCHAR(100) NOT NULL,
 country_code CHAR(3) NOT NULL,
 abbreviation VARCHAR(10) NOT NULL
);
GO
IF OBJECT_ID(N'dbo.competitor_rankings', N'U') IS NULL
CREATE TABLE dbo.competitor_rankings (
 rank_id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
 [rank] INT NOT NULL,
 movement INT NOT NULL,
 points INT NOT NULL,
 competitions_played INT NOT NULL,
 competitor_id VARCHAR(50) NOT NULL,
 CONSTRAINT fk_rankings_competitor FOREIGN KEY(competitor_id) REFERENCES dbo.competitors(competitor_id)
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='idx_comp_category' AND object_id=OBJECT_ID('dbo.competitions'))
 CREATE INDEX idx_comp_category ON dbo.competitions(category_id);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='idx_comp_parent' AND object_id=OBJECT_ID('dbo.competitions'))
 CREATE INDEX idx_comp_parent ON dbo.competitions(parent_id);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='idx_comp_type' AND object_id=OBJECT_ID('dbo.competitions'))
 CREATE INDEX idx_comp_type ON dbo.competitions([type]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='idx_venues_complex' AND object_id=OBJECT_ID('dbo.venues'))
 CREATE INDEX idx_venues_complex ON dbo.venues(complex_id);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='idx_venues_country' AND object_id=OBJECT_ID('dbo.venues'))
 CREATE INDEX idx_venues_country ON dbo.venues(country_name);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='idx_rankings_rank' AND object_id=OBJECT_ID('dbo.competitor_rankings'))
 CREATE INDEX idx_rankings_rank ON dbo.competitor_rankings([rank]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='idx_rankings_points' AND object_id=OBJECT_ID('dbo.competitor_rankings'))
 CREATE INDEX idx_rankings_points ON dbo.competitor_rankings(points DESC);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='idx_rankings_competitor' AND object_id=OBJECT_ID('dbo.competitor_rankings'))
 CREATE INDEX idx_rankings_competitor ON dbo.competitor_rankings(competitor_id);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='idx_rankings_movement' AND object_id=OBJECT_ID('dbo.competitor_rankings'))
 CREATE INDEX idx_rankings_movement ON dbo.competitor_rankings(movement);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='idx_competitors_country' AND object_id=OBJECT_ID('dbo.competitors'))
 CREATE INDEX idx_competitors_country ON dbo.competitors(country);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='idx_competitors_code' AND object_id=OBJECT_ID('dbo.competitors'))
 CREATE INDEX idx_competitors_code ON dbo.competitors(country_code);
GO
