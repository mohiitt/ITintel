-- Allow multiple state observations; use surrogate key.
ALTER TABLE marts.ticket_state_history DROP CONSTRAINT IF EXISTS ticket_state_history_pkey;
ALTER TABLE marts.ticket_state_history ADD COLUMN IF NOT EXISTS history_id BIGSERIAL;
-- Ensure history_id is unique/PK
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'ticket_state_history_pkey'
  ) THEN
    ALTER TABLE marts.ticket_state_history ADD PRIMARY KEY (history_id);
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_ticket_state_history_incident
  ON marts.ticket_state_history (source_track, incident_number, valid_from);
