-- ============================================================
-- SpotBot Migration — Run this ONCE on your existing database
-- before deploying the updated containers.
--
-- Usage (run from the trading-bot/ folder):
--   docker compose exec -T postgres psql -U trader -d tradingbot < migrate.sql
--
-- Or if using "docker exec" directly, first find the container name:
--   docker ps   →  look for the postgres container (e.g. trading-bot-postgres-1)
--   docker exec -i trading-bot-postgres-1 psql -U trader -d tradingbot < migrate.sql
-- ============================================================

-- ── USERS table new columns ────────────────────────────────
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_approved        BOOLEAN DEFAULT TRUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS can_trade          BOOLEAN DEFAULT TRUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_secret        VARCHAR(64);
ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_enabled       BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS email_notifications BOOLEAN DEFAULT TRUE;

-- Ensure the very first (admin) user is approved
UPDATE users SET is_approved = TRUE WHERE id = (SELECT MIN(id) FROM users);

-- ── TRADES table new columns ───────────────────────────────
ALTER TABLE trades ADD COLUMN IF NOT EXISTS paper_trade  BOOLEAN DEFAULT FALSE;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS trailing_sl  FLOAT;

-- ── STRATEGIES table new columns ──────────────────────────
ALTER TABLE strategies ADD COLUMN IF NOT EXISTS is_public          BOOLEAN DEFAULT FALSE;
ALTER TABLE strategies ADD COLUMN IF NOT EXISTS public_description VARCHAR(500);
ALTER TABLE strategies ADD COLUMN IF NOT EXISTS webhook_token      VARCHAR(64) UNIQUE;

-- Generate a unique webhook token for all existing strategies that don't have one
-- (PostgreSQL: use gen_random_uuid() as a stand-in for randomness)
UPDATE strategies
SET webhook_token = encode(gen_random_bytes(24), 'base64')
WHERE webhook_token IS NULL;

-- ── Done ───────────────────────────────────────────────────
SELECT 'Migration completed successfully.' AS status;
