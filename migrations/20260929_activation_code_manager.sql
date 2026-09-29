BEGIN;

ALTER TABLE activation_codes
    ADD COLUMN IF NOT EXISTS assigned_to TEXT,
    ADD COLUMN IF NOT EXISTS assigned_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS notes TEXT,
    ADD COLUMN IF NOT EXISTS batch_id TEXT,
    ADD COLUMN IF NOT EXISTS code_rotated_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS activation_code_audit (
    id BIGSERIAL PRIMARY KEY,
    band_id TEXT NOT NULL,
    action TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT 'admin',
    details TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_activation_codes_claimed
    ON activation_codes (claimed);
CREATE INDEX IF NOT EXISTS idx_activation_codes_assigned_to
    ON activation_codes (LOWER(assigned_to));
CREATE INDEX IF NOT EXISTS idx_activation_codes_batch_id
    ON activation_codes (batch_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_activation_codes_band_id_upper
    ON activation_codes (UPPER(band_id));
CREATE UNIQUE INDEX IF NOT EXISTS uq_activation_codes_code_upper
    ON activation_codes (UPPER(activation_code));

COMMIT;
