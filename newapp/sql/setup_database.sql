-- SQL Server Database Setup Script for wtnps-trade
-- Execute this script to create the database and configure permissions

-- Create database
IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = N'wtnps-trade')
BEGIN
    CREATE DATABASE [wtnps-trade]
    PRINT 'Database wtnps-trade created successfully'
END
ELSE
BEGIN
    PRINT 'Database wtnps-trade already exists'
END
GO

-- Use the database
USE [wtnps-trade]
GO

-- Create schema for application tables (optional, for better organization)
IF NOT EXISTS (SELECT * FROM sys.schemas WHERE name = 'trading')
BEGIN
    EXEC('CREATE SCHEMA trading')
    PRINT 'Schema trading created'
END
GO

-- Grant permissions (adjust username as needed)
-- For Windows Authentication (current user)
-- GRANT CONNECT TO [DOMAIN\Username]
-- GRANT SELECT, INSERT, UPDATE, DELETE, CREATE TABLE, ALTER ON SCHEMA::trading TO [DOMAIN\Username]
-- GO

PRINT 'Database setup complete!'
PRINT 'Connection string example:'
PRINT 'Server=localhost;Database=wtnps-trade;Trusted_Connection=yes;'
GO
