-- Migration: Add category column to products table
-- Date: 2026-02-11
-- Description: Adds a category field to products for better organization and filtering
--
-- Note: SQLite does not support IF NOT EXISTS for ALTER TABLE ADD COLUMN.
-- If re-running this migration, the ALTER TABLE statement will fail with "duplicate column name" error,
-- which is expected behavior. The CREATE INDEX statement is idempotent and will succeed.

-- Add category column (nullable to support existing products)
-- Note: This will fail if the column already exists (SQLite limitation)
ALTER TABLE products ADD COLUMN category VARCHAR(50);

-- Add index for faster category-based queries (idempotent)
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);

-- Optional: Update existing products with default categories based on name patterns
-- These updates only apply to products without a category (category IS NULL)
-- This prevents overwriting any manually set categories
-- Admins should review and update categories manually for edge cases
UPDATE products SET category = 'hoodies' WHERE category IS NULL AND LOWER(name) LIKE '%hoodie%';
UPDATE products SET category = 't-shirts' WHERE category IS NULL AND (LOWER(name) LIKE '%shirt%' OR LOWER(name) LIKE '%tshirt%' OR LOWER(name) LIKE '%t-shirt%');
UPDATE products SET category = 'stickers' WHERE category IS NULL AND (LOWER(name) LIKE '%sticker%' OR LOWER(name) LIKE '%decal%');
UPDATE products SET category = 'water-bottles' WHERE category IS NULL AND (LOWER(name) LIKE '%bottle%' OR LOWER(name) LIKE '%flask%' OR LOWER(name) LIKE '%hydro%');
