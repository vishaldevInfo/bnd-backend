-- Customer accounts, one-time email codes, audit log and identity review queue.
-- Everything lives in the "app" schema. Nothing here touches the Sage tables in public.

CREATE TABLE app.users (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    customerno          varchar(20)  NOT NULL,  -- Sage customer; one account per customer
    first_name          varchar(100) NOT NULL,
    last_name           varchar(100) NOT NULL,
    ssn_last4_hash      text         NOT NULL,  -- keyed HMAC of the last 4 digits; the full SSN is never stored
    email               varchar(254) NOT NULL CHECK (email = lower(email)),  -- verified by code
    phone               varchar(16)  NOT NULL,  -- E.164; stored for contact, not verified
    email_verified_at   timestamptz  NOT NULL,
    status              varchar(10)  NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'disabled')),
    created_at          timestamptz  NOT NULL DEFAULT now(),
    updated_at          timestamptz  NOT NULL DEFAULT now(),
    last_login_at       timestamptz
);
CREATE UNIQUE INDEX users_customerno_key ON app.users (customerno);
CREATE UNIQUE INDEX users_email_key ON app.users (email);
CREATE UNIQUE INDEX users_phone_key ON app.users (phone);

CREATE TABLE app.otp_codes (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      uuid REFERENCES app.users (id) ON DELETE CASCADE,  -- null during registration
    challenge_id uuid         NOT NULL,  -- one verification attempt; at most one live code
    email        varchar(254) NOT NULL,
    purpose      varchar(10)  NOT NULL CHECK (purpose IN ('register', 'login')),
    code_hash    text         NOT NULL,  -- keyed HMAC, never the code itself
    expires_at   timestamptz  NOT NULL,
    attempts     integer      NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    consumed_at  timestamptz,
    created_at   timestamptz  NOT NULL DEFAULT now()
);
CREATE INDEX otp_codes_challenge_idx ON app.otp_codes (challenge_id);

CREATE TABLE app.auth_audit_log (
    id          bigserial PRIMARY KEY,
    user_id     uuid REFERENCES app.users (id) ON DELETE SET NULL,
    event       varchar(20) NOT NULL CHECK (event IN (
                    'lookup_attempt', 'lookup_match', 'lookup_multi_match', 'otp_sent', 'otp_verified',
                    'otp_failed', 'login', 'logout', 'admin_login')),
    ip          text,
    user_agent  varchar(255),
    created_at  timestamptz NOT NULL DEFAULT now(),
    metadata    jsonb       NOT NULL DEFAULT '{}'::jsonb  -- outcome labels only: never SSN or codes
);
CREATE INDEX auth_audit_log_user_idx ON app.auth_audit_log (user_id, created_at);

CREATE TABLE app.identity_review_queue (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    submitted_first_name    varchar(100) NOT NULL,
    submitted_last_name     varchar(100) NOT NULL,
    ssn_last4_hash          text         NOT NULL,
    candidate_customernos   jsonb        NOT NULL,
    status                  varchar(10)  NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'resolved')),
    created_at              timestamptz  NOT NULL DEFAULT now()
);
CREATE INDEX identity_review_queue_status_idx ON app.identity_review_queue (status, created_at);
