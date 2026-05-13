-- ROADMAP #1C — LinkedIn Company Data
-- Adds an optional linkedin_url column to the competitors table.
-- The crawler can discover this via Google search, but a manually-supplied
-- value is more reliable (LinkedIn aggressively blocks scrapers).
--
-- Run this in the Supabase SQL Editor (Dashboard → SQL Editor → New Query).
-- Safe to re-run: uses IF NOT EXISTS.

ALTER TABLE competitors
  ADD COLUMN IF NOT EXISTS linkedin_url VARCHAR(2048);

COMMENT ON COLUMN competitors.linkedin_url IS
  'Optional LinkedIn company page URL. If set, the crawler fetches it directly. If null, the crawler tries Google search discovery.';
