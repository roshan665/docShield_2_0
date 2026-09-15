-- ==============================================================================
-- DOCSHIELD DEMO ACCOUNTS SEED (SUPABASE AUTH & PROFILES)
-- Run this in your Supabase SQL Editor to instantly provision all 3 demo accounts.
-- ==============================================================================

INSERT INTO auth.users (
    instance_id,
    id,
    aud,
    role,
    email,
    encrypted_password,
    email_confirmed_at,
    raw_app_meta_data,
    raw_user_meta_data,
    created_at,
    updated_at
) VALUES 
(
    '00000000-0000-0000-0000-000000000000',
    gen_random_uuid(),
    'authenticated',
    'authenticated',
    'admin@docshield.gov.in',
    crypt('Admin@12345', gen_salt('bf')),
    now(),
    '{"provider":"email","providers":["email"]}',
    '{"full_name":"DOCSHIELD System Administrator","role":"Admin","department":"Information Technology & Cyber Security","designation":"Chief System Security Officer","employee_id":"EMP-ADMIN-001"}',
    now(),
    now()
),
(
    '00000000-0000-0000-0000-000000000000',
    gen_random_uuid(),
    'authenticated',
    'authenticated',
    'officer@docshield.gov.in',
    crypt('Officer@12345', gen_salt('bf')),
    now(),
    '{"provider":"email","providers":["email"]}',
    '{"full_name":"Inspector Rajesh Sharma","role":"Officer","department":"Cybercrime Investigation Division","designation":"Senior Inspector","employee_id":"EMP-INV-001"}',
    now(),
    now()
),
(
    '00000000-0000-0000-0000-000000000000',
    gen_random_uuid(),
    'authenticated',
    'authenticated',
    'advocate@docshield.gov.in',
    crypt('Advocate@12345', gen_salt('bf')),
    now(),
    '{"provider":"email","providers":["email"]}',
    '{"full_name":"Advocate Priya Rao","role":"Advocate","department":"Directorate of Prosecution","designation":"Public Prosecutor","employee_id":"EMP-LEG-001"}',
    now(),
    now()
)
ON CONFLICT (email) DO UPDATE SET
    encrypted_password = EXCLUDED.encrypted_password,
    raw_user_meta_data = EXCLUDED.raw_user_meta_data,
    email_confirmed_at = COALESCE(auth.users.email_confirmed_at, now()),
    updated_at = now();

-- Ensure profiles are synced with correct roles
INSERT INTO public.profiles (id, employee_id, full_name, email, role, department, designation)
SELECT 
    u.id,
    COALESCE(u.raw_user_meta_data->>'employee_id', 'EMP-' || upper(substr(u.id::text, 1, 8))),
    COALESCE(u.raw_user_meta_data->>'full_name', split_part(u.email, '@', 1)),
    u.email,
    (u.raw_user_meta_data->>'role')::app_role_enum,
    u.raw_user_meta_data->>'department',
    u.raw_user_meta_data->>'designation'
FROM auth.users u
WHERE u.email IN ('admin@docshield.gov.in', 'officer@docshield.gov.in', 'advocate@docshield.gov.in')
ON CONFLICT (id) DO UPDATE SET
    email = EXCLUDED.email,
    full_name = EXCLUDED.full_name,
    role = EXCLUDED.role;

