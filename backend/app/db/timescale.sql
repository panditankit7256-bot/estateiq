-- Optional: run once on PostgreSQL with the TimescaleDB extension to turn `readings` into a hypertable.
-- Run AFTER the API has started once (it creates the tables):
-- docker compose exec db psql -U estateiq -d estateiq -f /opt/timescale.sql
CREATE EXTENSION IF NOT EXISTS timescaledb;
ALTER TABLE readings DROP CONSTRAINT IF EXISTS readings_pkey;
ALTER TABLE readings ADD PRIMARY KEY (id, ts);
SELECT create_hypertable('readings', 'ts', if_not_exists => TRUE, migrate_data => TRUE);
