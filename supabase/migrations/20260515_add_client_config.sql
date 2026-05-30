CREATE TABLE IF NOT EXISTS client_configs (
    id          TEXT PRIMARY KEY DEFAULT 'default',
    config      JSONB NOT NULL,
    updated_at  TIMESTAMPTZ DEFAULT now()
);
