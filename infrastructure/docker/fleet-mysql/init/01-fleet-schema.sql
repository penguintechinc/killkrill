-- Fleet MySQL initialization script
-- This script sets up the basic database structure for Fleet

-- Create the Fleet database if it doesn't exist
CREATE DATABASE IF NOT EXISTS fleet;

-- Use the Fleet database
USE fleet;

-- Grant privileges to the Fleet user
GRANT ALL PRIVILEGES ON fleet.* TO 'fleet'@'%';
FLUSH PRIVILEGES;

-- Set charset and collation for proper UTF-8 support
ALTER DATABASE fleet CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Basic Fleet tables will be created by Fleet server on first startup
-- This script ensures the database is ready for Fleet migrations