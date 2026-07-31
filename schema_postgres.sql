-- ============================================================
-- EmpowerBands PostgreSQL Database Schema
-- File: schema_postgres.sql
-- ============================================================

BEGIN;

-- ============================================================
-- BULK-PROVISIONED EMPOWERBANDS
-- ============================================================

CREATE TABLE IF NOT EXISTS bands (
    band_id VARCHAR(50) PRIMARY KEY,

    activation_token VARCHAR(255) NOT NULL UNIQUE,

    nfc_url TEXT NOT NULL,

    partner_org VARCHAR(255) NOT NULL,

    batch_number VARCHAR(100) NOT NULL,

    status VARCHAR(20) NOT NULL DEFAULT 'unassigned',

    assigned_customer_id VARCHAR(100),

    date_created TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    date_activated TIMESTAMPTZ,

    qc_tested_nfc BOOLEAN NOT NULL DEFAULT FALSE,

    qc_tested_qr BOOLEAN NOT NULL DEFAULT FALSE,

    qc_status VARCHAR(20) NOT NULL DEFAULT 'pending',

    qc_notes TEXT,

    qc_updated_at TIMESTAMPTZ,

    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT bands_status_check
        CHECK (
            status IN (
                'unassigned',
                'active',
                'lost',
                'replaced'
            )
        ),

    CONSTRAINT bands_qc_status_check
        CHECK (
            qc_status IN (
                'pending',
                'passed',
                'failed'
            )
        )
);


-- ============================================================
-- AUDIT LOG
-- Records administrative and customer actions.
-- ============================================================

CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,

    actor VARCHAR(255) NOT NULL DEFAULT 'system',

    action VARCHAR(255) NOT NULL,

    target VARCHAR(255),

    details TEXT,

    ip_address VARCHAR(100),

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_bands_activation_token
    ON bands (activation_token);

CREATE INDEX IF NOT EXISTS idx_bands_batch_number
    ON bands (batch_number);

CREATE INDEX IF NOT EXISTS idx_bands_partner_org
    ON bands (partner_org);

CREATE INDEX IF NOT EXISTS idx_bands_status
    ON bands (status);

CREATE INDEX IF NOT EXISTS idx_bands_qc_status
    ON bands (qc_status);

CREATE INDEX IF NOT EXISTS idx_bands_date_created
    ON bands (date_created DESC);

CREATE INDEX IF NOT EXISTS idx_bands_date_activated
    ON bands (date_activated DESC);

CREATE INDEX IF NOT EXISTS idx_bands_partner_batch
    ON bands (partner_org, batch_number);

CREATE INDEX IF NOT EXISTS idx_audit_log_created_at
    ON audit_log (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_audit_log_actor
    ON audit_log (actor);

CREATE INDEX IF NOT EXISTS idx_audit_log_action
    ON audit_log (action);

CREATE INDEX IF NOT EXISTS idx_audit_log_target
    ON audit_log (target);


-- ============================================================
-- AUTOMATIC UPDATED-AT FUNCTION
-- ============================================================

CREATE OR REPLACE FUNCTION update_bands_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


DROP TRIGGER IF EXISTS bands_updated_at_trigger ON bands;

CREATE TRIGGER bands_updated_at_trigger
BEFORE UPDATE ON bands
FOR EACH ROW
EXECUTE FUNCTION update_bands_updated_at();


COMMIT;
