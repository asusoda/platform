-- Migration: Add category column to products table
-- Date: 2026-02-11
-- Description: Adds a category field to products for better organization and filtering

-- Add category column (nullable to support existing products)
ALTER TABLE products ADD COLUMN category VARCHAR(50);

-- Optional: Add index for faster category-based queries
CREATE INDEX idx_products_category ON products(category);

-- Optional: Update existing products with default categories based on name patterns
-- This is a best-effort migration - admins should review and update categories manually
UPDATE products SET category = 'hoodies' WHERE LOWER(name) LIKE '%hoodie%';
UPDATE products SET category = 't-shirts' WHERE LOWER(name) LIKE '%shirt%' OR LOWER(name) LIKE '%tshirt%' OR LOWER(name) LIKE '%t-shirt%';
UPDATE products SET category = 'stickers' WHERE LOWER(name) LIKE '%sticker%' OR LOWER(name) LIKE '%decal%';
UPDATE products SET category = 'water-bottles' WHERE LOWER(name) LIKE '%bottle%' OR LOWER(name) LIKE '%flask%' OR LOWER(name) LIKE '%hydro%';
