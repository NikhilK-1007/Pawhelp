-- PawHelp MySQL Database & Table Schema
-- Open and execute this in MySQL Workbench 8.0 if you wish to set up manually.

CREATE DATABASE IF NOT EXISTS `pawhelp_db` 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

USE `pawhelp_db`;

CREATE TABLE IF NOT EXISTS `reports` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `animal_type` VARCHAR(50) NOT NULL,
    `problem` VARCHAR(50) NOT NULL,
    `description` TEXT NOT NULL,
    `location` VARCHAR(255) NOT NULL,
    `latitude` DOUBLE NULL,
    `longitude` DOUBLE NULL,
    `maps_url` VARCHAR(500) NULL,
    `photo_path` VARCHAR(500) NULL,
    `created_at` VARCHAR(50) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Query to view all submitted reports:
-- SELECT * FROM `reports` ORDER BY `id` DESC;
