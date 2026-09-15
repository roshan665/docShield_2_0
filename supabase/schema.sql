-- ==============================================================================
-- DOCSHIELD 2.0 - SUPABASE PRODUCTION DATABASE SCHEMA & RLS SETUP
-- ==============================================================================
-- Run this entire script in your Supabase Project's SQL Editor (Dashboard -> SQL Editor -> New query)
-- It creates all required tables, triggers, sequences, storage buckets, and RLS policies.
-- ==============================================================================

-- 1. Enable Required Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 2. Define Custom Enums
DO $$ BEGIN
    CREATE TYPE app_role_enum AS ENUM ('Admin', 'Officer', 'Advocate');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- 3. Public User Profiles Table (Linked to auth.users)
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    employee_id VARCHAR(50) UNIQUE NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    role app_role_enum NOT NULL DEFAULT 'Officer',
    department VARCHAR(100),
    designation VARCHAR(100),
    phone VARCHAR(20),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_locked BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- Trigger: Automatically create public profile on new auth.users signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER 
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth, pg_temp
AS $$
DECLARE
    user_role public.app_role_enum := 'Officer';
    raw_role text;
    v_name text;
    v_dept text;
    v_desig text;
BEGIN
    raw_role := LOWER(COALESCE(NEW.raw_user_meta_data->>'role', ''));
    IF raw_role = 'admin' OR LOWER(NEW.email) LIKE '%admin%' THEN
        user_role := 'Admin'::public.app_role_enum;
        v_name := COALESCE(NULLIF(NEW.raw_user_meta_data->>'full_name', ''), 'DOCSHIELD System Administrator');
        v_dept := COALESCE(NULLIF(NEW.raw_user_meta_data->>'department', ''), 'Information Technology & Cyber Security');
        v_desig := COALESCE(NULLIF(NEW.raw_user_meta_data->>'designation', ''), 'Chief System Security Officer');
    ELSIF raw_role = 'advocate' OR LOWER(NEW.email) LIKE '%advocate%' OR LOWER(NEW.email) LIKE '%legal%' THEN
        user_role := 'Advocate'::public.app_role_enum;
        v_name := COALESCE(NULLIF(NEW.raw_user_meta_data->>'full_name', ''), 'Advocate Priya Rao');
        v_dept := COALESCE(NULLIF(NEW.raw_user_meta_data->>'department', ''), 'Directorate of Prosecution');
        v_desig := COALESCE(NULLIF(NEW.raw_user_meta_data->>'designation', ''), 'Public Prosecutor');
    ELSE
        user_role := 'Officer'::public.app_role_enum;
        v_name := COALESCE(NULLIF(NEW.raw_user_meta_data->>'full_name', ''), 'Inspector Rajesh Sharma');
        v_dept := COALESCE(NULLIF(NEW.raw_user_meta_data->>'department', ''), 'Cybercrime Investigation Division');
        v_desig := COALESCE(NULLIF(NEW.raw_user_meta_data->>'designation', ''), 'Senior Inspector');
    END IF;

    INSERT INTO public.profiles (
        id, 
        employee_id, 
        full_name, 
        email, 
        role, 
        department, 
        designation
    )
    VALUES (
        NEW.id,
        COALESCE(NULLIF(NEW.raw_user_meta_data->>'employee_id', ''), 'EMP-' || upper(substr(NEW.id::text, 1, 8))),
        v_name,
        NEW.email,
        user_role,
        v_dept,
        v_desig
    )
    ON CONFLICT (id) DO UPDATE SET
        email = EXCLUDED.email,
        full_name = EXCLUDED.full_name,
        role = EXCLUDED.role,
        department = EXCLUDED.department,
        designation = EXCLUDED.designation;
        
    RETURN NEW;
EXCEPTION WHEN OTHERS THEN
    INSERT INTO public.profiles (id, employee_id, full_name, email, role)
    VALUES (
        NEW.id,
        'EMP-' || upper(substr(NEW.id::text, 1, 8)),
        split_part(NEW.email, '@', 1),
        NEW.email,
        'Officer'::public.app_role_enum
    )
    ON CONFLICT (id) DO NOTHING;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- 4. Cases Table
CREATE SEQUENCE IF NOT EXISTS case_number_seq START WITH 1001;

CREATE TABLE IF NOT EXISTS public.cases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_number VARCHAR(100) UNIQUE NOT NULL,
    fir_number VARCHAR(100),
    title VARCHAR(500) NOT NULL,
    description TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'under_investigation', 'pending_review', 'pending_legal', 'closed', 'archived')),
    priority VARCHAR(20) NOT NULL DEFAULT 'medium' CHECK (priority IN ('critical', 'high', 'medium', 'low')),
    category VARCHAR(100),
    police_station VARCHAR(255),
    district VARCHAR(100),
    state VARCHAR(100),
    investigating_officer_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    created_by UUID NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT,
    closed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- Trigger: Auto-generate case_number if not provided (e.g. CR-2026-1001)
CREATE OR REPLACE FUNCTION generate_case_number()
RETURNS TRIGGER 
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
    IF NEW.case_number IS NULL OR trim(NEW.case_number) = '' THEN
        NEW.case_number := 'CR-' || to_char(now(), 'YYYY') || '-' || nextval('case_number_seq')::text;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_generate_case_number ON public.cases;
CREATE TRIGGER trg_generate_case_number
    BEFORE INSERT ON public.cases
    FOR EACH ROW EXECUTE FUNCTION generate_case_number();

-- 5. Case Members Table (Access Scoping & Team Enrollment)
CREATE TABLE IF NOT EXISTS public.case_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES public.cases(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    role_in_case VARCHAR(50) NOT NULL CHECK (role_in_case IN ('lead_investigator', 'investigator', 'forensic_analyst', 'legal_counsel', 'supervisor', 'reviewer')),
    added_by UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    added_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    removed_at TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT uq_case_member_pair UNIQUE (case_id, user_id)
);

-- Trigger: Automatically enroll creator as lead_investigator upon case creation
CREATE OR REPLACE FUNCTION auto_enroll_case_creator()
RETURNS TRIGGER 
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
    INSERT INTO public.case_members (case_id, user_id, role_in_case, added_by, is_active)
    VALUES (NEW.id, NEW.created_by, 'lead_investigator', NEW.created_by, TRUE)
    ON CONFLICT (case_id, user_id) DO NOTHING;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_auto_enroll_case_creator ON public.cases;
CREATE TRIGGER trg_auto_enroll_case_creator
    AFTER INSERT ON public.cases
    FOR EACH ROW EXECUTE FUNCTION auto_enroll_case_creator();

-- 6. Evidence & Custody Events Tables
CREATE TABLE IF NOT EXISTS public.evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES public.cases(id) ON DELETE RESTRICT,
    evidence_number VARCHAR(100) UNIQUE NOT NULL,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    evidence_type VARCHAR(100) NOT NULL DEFAULT 'digital_document',
    status VARCHAR(50) NOT NULL DEFAULT 'registered',
    sensitivity_level VARCHAR(50) NOT NULL DEFAULT 'standard',
    original_file_hash VARCHAR(64),
    current_file_hash VARCHAR(64),
    integrity_status VARCHAR(20) NOT NULL DEFAULT 'verified',
    current_custodian_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT,
    pending_custodian_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    transfer_pending BOOLEAN NOT NULL DEFAULT FALSE,
    transfer_reason TEXT,
    storage_key VARCHAR(500),
    storage_bucket VARCHAR(100) DEFAULT 'evidence-vault',
    mime_type VARCHAR(100),
    file_size_bytes BIGINT,
    collection_date TIMESTAMPTZ,
    collection_location TEXT,
    source VARCHAR(500),
    registered_by_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT,
    archived_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE TABLE IF NOT EXISTS public.evidence_custody_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evidence_id UUID NOT NULL REFERENCES public.evidence(id) ON DELETE RESTRICT,
    case_id UUID NOT NULL REFERENCES public.cases(id) ON DELETE RESTRICT,
    event_type VARCHAR(50) NOT NULL,
    from_user_id UUID REFERENCES public.profiles(id) ON DELETE RESTRICT,
    to_user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT,
    reason TEXT NOT NULL,
    location VARCHAR(500),
    notes TEXT,
    file_hash_at_event VARCHAR(64),
    previous_event_hash VARCHAR(64) NOT NULL,
    event_hash VARCHAR(64) NOT NULL,
    acknowledgement_status VARCHAR(50) NOT NULL DEFAULT 'acknowledged',
    acknowledged_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- 7. Documents & Document Versions Tables
CREATE TABLE IF NOT EXISTS public.documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES public.cases(id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    document_type VARCHAR(100) NOT NULL DEFAULT 'other',
    classification VARCHAR(50) NOT NULL DEFAULT 'internal',
    status VARCHAR(50) NOT NULL DEFAULT 'processed',
    current_version_id UUID,
    original_filename VARCHAR(500),
    mime_type VARCHAR(100),
    file_size_bytes BIGINT,
    uploaded_by UUID NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT,
    is_evidence BOOLEAN NOT NULL DEFAULT FALSE,
    evidence_id UUID,
    ai_processed BOOLEAN NOT NULL DEFAULT FALSE,
    ocr_text TEXT,
    summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE TABLE IF NOT EXISTS public.document_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES public.documents(id) ON DELETE CASCADE,
    version_number INT NOT NULL,
    storage_key VARCHAR(500) NOT NULL,
    storage_bucket VARCHAR(100) NOT NULL DEFAULT 'case-documents',
    file_hash_sha256 VARCHAR(64) NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    original_filename VARCHAR(500) NOT NULL,
    change_reason TEXT,
    uploaded_by UUID NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT,
    integrity_status VARCHAR(20) NOT NULL DEFAULT 'verified',
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT uq_document_version_number UNIQUE (document_id, version_number)
);

-- 8. Immutable Audit Trail Table
CREATE TABLE IF NOT EXISTS public.audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100) NOT NULL,
    resource_id UUID,
    case_id UUID REFERENCES public.cases(id) ON DELETE SET NULL,
    details JSONB,
    result VARCHAR(20) NOT NULL DEFAULT 'success',
    ip_address VARCHAR(45),
    user_agent VARCHAR(500),
    session_id VARCHAR(255),
    previous_event_hash VARCHAR(64),
    event_hash VARCHAR(64) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- 9. Storage Buckets (Supabase Storage)
INSERT INTO storage.buckets (id, name, public)
VALUES ('case-documents', 'case-documents', false)
ON CONFLICT (id) DO NOTHING;

INSERT INTO storage.buckets (id, name, public)
VALUES ('evidence-vault', 'evidence-vault', false)
ON CONFLICT (id) DO NOTHING;

-- ==============================================================================
-- 10. ROW LEVEL SECURITY (RLS) POLICIES
-- ==============================================================================
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.case_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.evidence_custody_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.document_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_events ENABLE ROW LEVEL SECURITY;

-- Helper function to fetch current authenticated user's canonical role
CREATE OR REPLACE FUNCTION public.current_user_role()
RETURNS app_role_enum AS $$
    SELECT COALESCE(
        (SELECT role FROM public.profiles WHERE id = auth.uid()),
        'Officer'::app_role_enum
    );
$$ LANGUAGE sql STABLE SECURITY DEFINER;

-- Profiles: Authenticated users can view active team members; Admins have full access
DROP POLICY IF EXISTS "profiles_select_policy" ON public.profiles;
CREATE POLICY "profiles_select_policy" ON public.profiles
    FOR SELECT TO authenticated
    USING (is_active = TRUE);

DROP POLICY IF EXISTS "profiles_admin_policy" ON public.profiles;
CREATE POLICY "profiles_admin_policy" ON public.profiles
    FOR ALL TO authenticated
    USING (public.current_user_role() = 'Admin');

-- Helper function to check case membership without triggering RLS recursion
CREATE OR REPLACE FUNCTION public.is_case_member(p_case_id UUID, p_user_id UUID)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.case_members
        WHERE case_id = p_case_id
          AND user_id = p_user_id
          AND is_active = TRUE
    );
$$;

-- Helper function to check case access (creator, officer, or member) without recursion
CREATE OR REPLACE FUNCTION public.can_access_case(p_case_id UUID, p_user_id UUID)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.cases c
        WHERE c.id = p_case_id
          AND (
              c.created_by = p_user_id
              OR c.investigating_officer_id = p_user_id
              OR public.is_case_member(c.id, p_user_id)
          )
    );
$$;

-- Cases:
-- Admin: Sees all cases across the system
-- Officer / Advocate: Sees cases where they are creator, investigating officer, or active case member
DROP POLICY IF EXISTS "cases_select_policy" ON public.cases;
CREATE POLICY "cases_select_policy" ON public.cases
    FOR SELECT TO authenticated
    USING (
        public.current_user_role() = 'Admin'
        OR created_by = auth.uid()
        OR investigating_officer_id = auth.uid()
        OR public.is_case_member(id, auth.uid())
    );

-- Cases: Admin and Officer can register cases
DROP POLICY IF EXISTS "cases_insert_policy" ON public.cases;
CREATE POLICY "cases_insert_policy" ON public.cases
    FOR INSERT TO authenticated
    WITH CHECK (
        public.current_user_role() IN ('Admin', 'Officer')
        AND created_by = auth.uid()
    );

-- Cases: Admin, Creator, Investigating Officer, or Member can update details
DROP POLICY IF EXISTS "cases_update_policy" ON public.cases;
CREATE POLICY "cases_update_policy" ON public.cases
    FOR UPDATE TO authenticated
    USING (
        public.current_user_role() = 'Admin'
        OR created_by = auth.uid()
        OR investigating_officer_id = auth.uid()
        OR public.is_case_member(id, auth.uid())
    );

-- Case Members: Scoped visibility (No self-referential subquery on case_members!)
DROP POLICY IF EXISTS "case_members_select_policy" ON public.case_members;
CREATE POLICY "case_members_select_policy" ON public.case_members
    FOR SELECT TO authenticated
    USING (
        public.current_user_role() = 'Admin'
        OR user_id = auth.uid()
        OR public.can_access_case(case_id, auth.uid())
    );

DROP POLICY IF EXISTS "case_members_write_policy" ON public.case_members;
DROP POLICY IF EXISTS "case_members_insert_policy" ON public.case_members;
CREATE POLICY "case_members_insert_policy" ON public.case_members
    FOR INSERT TO authenticated
    WITH CHECK (
        public.current_user_role() IN ('Admin', 'Officer')
        OR user_id = auth.uid()
    );

DROP POLICY IF EXISTS "case_members_update_policy" ON public.case_members;
CREATE POLICY "case_members_update_policy" ON public.case_members
    FOR UPDATE TO authenticated
    USING (
        public.current_user_role() IN ('Admin', 'Officer')
    );

DROP POLICY IF EXISTS "case_members_delete_policy" ON public.case_members;
CREATE POLICY "case_members_delete_policy" ON public.case_members
    FOR DELETE TO authenticated
    USING (
        public.current_user_role() = 'Admin'
    );

-- Audit Events: Authenticated users can insert; view scoped to cases they belong to
DROP POLICY IF EXISTS "audit_events_insert_policy" ON public.audit_events;
CREATE POLICY "audit_events_insert_policy" ON public.audit_events
    FOR INSERT TO authenticated
    WITH CHECK (true);

DROP POLICY IF EXISTS "audit_events_select_policy" ON public.audit_events;
CREATE POLICY "audit_events_select_policy" ON public.audit_events
    FOR SELECT TO authenticated
    USING (
        public.current_user_role() = 'Admin'
        OR case_id IS NULL
        OR public.can_access_case(case_id, auth.uid())
    );

-- Evidence & Documents policies
DROP POLICY IF EXISTS "evidence_select_policy" ON public.evidence;
CREATE POLICY "evidence_select_policy" ON public.evidence
    FOR SELECT TO authenticated
    USING (
        public.current_user_role() = 'Admin'
        OR public.can_access_case(case_id, auth.uid())
    );

DROP POLICY IF EXISTS "evidence_write_policy" ON public.evidence;
CREATE POLICY "evidence_write_policy" ON public.evidence
    FOR ALL TO authenticated
    USING (
        public.current_user_role() IN ('Admin', 'Officer')
    );

DROP POLICY IF EXISTS "documents_select_policy" ON public.documents;
CREATE POLICY "documents_select_policy" ON public.documents
    FOR SELECT TO authenticated
    USING (
        public.current_user_role() = 'Admin'
        OR public.can_access_case(case_id, auth.uid())
    );

DROP POLICY IF EXISTS "documents_write_policy" ON public.documents;
CREATE POLICY "documents_write_policy" ON public.documents
    FOR ALL TO authenticated
    USING (
        public.current_user_role() IN ('Admin', 'Officer')
    );

-- ==============================================================================
-- 11. ROLES & PERMISSIONS GRANTS (PostgREST API & Auth Access)
-- ==============================================================================
GRANT USAGE ON SCHEMA public TO postgres, anon, authenticated, service_role, supabase_auth_admin;

GRANT ALL ON ALL TABLES IN SCHEMA public TO postgres, anon, authenticated, service_role, supabase_auth_admin;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO postgres, anon, authenticated, service_role, supabase_auth_admin;
GRANT ALL ON ALL ROUTINES IN SCHEMA public TO postgres, anon, authenticated, service_role, supabase_auth_admin;

ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO postgres, anon, authenticated, service_role, supabase_auth_admin;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO postgres, anon, authenticated, service_role, supabase_auth_admin;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON ROUTINES TO postgres, anon, authenticated, service_role, supabase_auth_admin;

-- ==============================================================================
-- 12. DEMO ACCOUNTS SEED (Admin, Officer, Advocate)
-- ==============================================================================
INSERT INTO auth.users (
    instance_id, id, aud, role, email, encrypted_password, email_confirmed_at,
    raw_app_meta_data, raw_user_meta_data, created_at, updated_at
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

-- Ensure profiles exist with explicit roles
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



