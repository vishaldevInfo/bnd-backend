-- Moves a database created by the earlier SMS-era 001 to the email-only schema.
-- On a fresh database, every step below is a no-op.

ALTER TABLE app.otp_codes ADD COLUMN IF NOT EXISTS email varchar(254);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema = 'app' AND table_name = 'otp_codes' AND column_name = 'channel') THEN
        DELETE FROM app.otp_codes WHERE channel <> 'email';  -- old SMS codes; all expired
        UPDATE app.otp_codes SET email = destination WHERE email IS NULL;
        ALTER TABLE app.otp_codes DROP COLUMN channel, DROP COLUMN destination;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema = 'app' AND table_name = 'users' AND column_name = 'phone_verified_at') THEN
        ALTER TABLE app.users DROP COLUMN phone_verified_at;
    END IF;
END $$;

ALTER TABLE app.otp_codes ALTER COLUMN email SET NOT NULL;
CREATE INDEX IF NOT EXISTS otp_codes_challenge_idx ON app.otp_codes (challenge_id);

UPDATE app.users SET email_verified_at = COALESCE(email_verified_at, created_at);
ALTER TABLE app.users ALTER COLUMN email_verified_at SET NOT NULL;
