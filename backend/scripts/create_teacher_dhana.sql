-- One-time teacher registration for Lotus Smart Study.
-- The password value below is an application-compatible scrypt hash generated
-- with app.security.hash_password. No plaintext password is stored here.
-- Run against the lotus_smart_study PostgreSQL database after migrations.

BEGIN;

INSERT INTO users (
    id,
    name,
    login_identifier,
    password_hash,
    role,
    status,
    must_change_password,
    created_at,
    updated_at
)
SELECT
    '98303f2b-3733-4aaf-b516-97509557246c'::uuid,
    'Dhana',
    'lotussmartstudy@gmail.com',
    'scrypt$16384$8$1$X3YYnd80ykJ7cWSSLyOGGQ==$MU37wP8cyhIY13K6K-Nl6WSTXS9H9YlXIYXGpUhbKmA=',
    'TEACHER'::role,
    'ACTIVE'::user_status,
    false,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
WHERE NOT EXISTS (
    SELECT 1
    FROM users AS existing_user
    WHERE lower(existing_user.login_identifier) = 'lotussmartstudy@gmail.com'
)
AND NOT EXISTS (
    SELECT 1
    FROM student_profiles AS existing_profile
    WHERE existing_profile.email IS NOT NULL
      AND lower(existing_profile.email) = 'lotussmartstudy@gmail.com'
)
ON CONFLICT (login_identifier) DO NOTHING;

COMMIT;
