-- PROJECT RESILIENCE-ALPHA : schema PayAlpha (donnees fictives)
-- Aucune donnee bancaire reelle. Comptes et transactions a but de demonstration.

-- Extension pour gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ------------------------------------------------------------------ utilisateurs (auth)
CREATE TABLE IF NOT EXISTS auth_users (
    username      TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'user'
);

-- Identifiants fictifs de demonstration.
-- alice / bob : Demo#2026   |   ops : Ops#2026
INSERT INTO auth_users (username, password_hash, role) VALUES
  ('alice', '$2b$10$SEDkCynvHNmPuv0nKBJPZuNLkwaoytrkCzbSqQr8gi.y6RJ6unolq', 'user'),
  ('bob',   '$2b$10$p95vd/8s2Eoxt5ZgpZu4CuRcbakJ/dHQgu9DX7M6hfw7HZ3h2Zbnq', 'user'),
  ('ops',   '$2b$10$flbQpBCz5zjpzZ94iG/OZ.mkzt1tiWOj5eJQpbMmMfSZYcib4swRa', 'operator')
ON CONFLICT (username) DO NOTHING;

-- ------------------------------------------------------------------ comptes
CREATE TABLE IF NOT EXISTS accounts (
    id          BIGSERIAL PRIMARY KEY,
    owner       TEXT NOT NULL,
    iban_fake   TEXT NOT NULL UNIQUE,
    balance     NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (balance >= 0),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO accounts (owner, iban_fake, balance) VALUES
  ('alice', 'FR76-FAKE-0001', 5000.00),
  ('bob',   'FR76-FAKE-0002', 3000.00),
  ('merchant-cafe',  'FR76-FAKE-9001', 1000.00),
  ('merchant-store', 'FR76-FAKE-9002', 1000.00)
ON CONFLICT (iban_fake) DO NOTHING;

-- ------------------------------------------------------------------ transactions
CREATE TABLE IF NOT EXISTS transactions (
    id           BIGSERIAL PRIMARY KEY,
    reference    UUID NOT NULL DEFAULT gen_random_uuid(),
    src_iban     TEXT NOT NULL REFERENCES accounts(iban_fake),
    dst_iban     TEXT NOT NULL REFERENCES accounts(iban_fake),
    amount       NUMERIC(14,2) NOT NULL CHECK (amount > 0),
    status       TEXT NOT NULL DEFAULT 'posted',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tx_created_at ON transactions(created_at);
CREATE INDEX IF NOT EXISTS idx_tx_reference  ON transactions(reference);
