-- Apply before deploying the server-side Safety ID verification flow.
-- No customer records or activation inventory are changed.
BEGIN;
CREATE TABLE IF NOT EXISTS profile_verification_challenges (
    band_id TEXT PRIMARY KEY,
    challenge_id TEXT NOT NULL UNIQUE,
    code_hash TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS safety_pin_attempts (
    actor_hash TEXT PRIMARY KEY,
    attempts INTEGER NOT NULL DEFAULT 0,
    window_start TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
COMMIT;
