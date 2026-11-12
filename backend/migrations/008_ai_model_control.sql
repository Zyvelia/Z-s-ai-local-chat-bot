-- v0.8: apply after 007; backup database first. Safe to rerun.
BEGIN;
ALTER TABLE characters ADD COLUMN IF NOT EXISTS preferred_model VARCHAR(160);
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS inference_model VARCHAR(160);
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS temperature DOUBLE PRECISION;
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS top_p DOUBLE PRECISION;
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS context_window INTEGER;
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS generation_preset VARCHAR(32) NOT NULL DEFAULT 'balanced';



COMMIT;
