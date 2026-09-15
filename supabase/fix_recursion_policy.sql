-- ==============================================================================
-- IMMEDIATE FIX: INFINITE RECURSION IN POLICY FOR RELATION "case_members"
-- Run this script in Supabase SQL Editor to instantly fix the recursion bug.
-- ==============================================================================

-- 1. Helper security-definer function: checks active case membership without triggering RLS
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

-- 2. Helper security-definer function: checks case access (creator, officer, or member)
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

-- 3. Fix Case Members policies (Eliminates self-referential subquery on case_members)
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

-- 4. Fix Cases policies (Uses non-recursive is_case_member)
DROP POLICY IF EXISTS "cases_select_policy" ON public.cases;
CREATE POLICY "cases_select_policy" ON public.cases
    FOR SELECT TO authenticated
    USING (
        public.current_user_role() = 'Admin'
        OR created_by = auth.uid()
        OR investigating_officer_id = auth.uid()
        OR public.is_case_member(id, auth.uid())
    );

DROP POLICY IF EXISTS "cases_insert_policy" ON public.cases;
CREATE POLICY "cases_insert_policy" ON public.cases
    FOR INSERT TO authenticated
    WITH CHECK (
        public.current_user_role() IN ('Admin', 'Officer')
        AND created_by = auth.uid()
    );

DROP POLICY IF EXISTS "cases_update_policy" ON public.cases;
CREATE POLICY "cases_update_policy" ON public.cases
    FOR UPDATE TO authenticated
    USING (
        public.current_user_role() = 'Admin'
        OR created_by = auth.uid()
        OR investigating_officer_id = auth.uid()
        OR public.is_case_member(id, auth.uid())
    );

-- 5. Fix Audit Events policies (Uses non-recursive can_access_case)
DROP POLICY IF EXISTS "audit_events_select_policy" ON public.audit_events;
CREATE POLICY "audit_events_select_policy" ON public.audit_events
    FOR SELECT TO authenticated
    USING (
        public.current_user_role() = 'Admin'
        OR case_id IS NULL
        OR public.can_access_case(case_id, auth.uid())
    );

DROP POLICY IF EXISTS "audit_events_insert_policy" ON public.audit_events;
CREATE POLICY "audit_events_insert_policy" ON public.audit_events
    FOR INSERT TO authenticated
    WITH CHECK (true);

-- 6. Evidence & Documents policies
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

-- 7. Ensure execution grants
GRANT EXECUTE ON FUNCTION public.is_case_member(UUID, UUID) TO postgres, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.can_access_case(UUID, UUID) TO postgres, anon, authenticated, service_role;

-- 8. Fix existing profiles roles (Sync roles based on email)
UPDATE public.profiles 
SET 
    role = 'Admin'::public.app_role_enum,
    full_name = 'DOCSHIELD System Administrator',
    designation = 'Chief System Security Officer',
    department = 'Information Technology & Cyber Security'
WHERE LOWER(email) LIKE '%admin%';

UPDATE public.profiles 
SET 
    role = 'Advocate'::public.app_role_enum,
    full_name = 'Advocate Priya Rao',
    designation = 'Public Prosecutor',
    department = 'Directorate of Prosecution'
WHERE LOWER(email) LIKE '%advocate%' OR LOWER(email) LIKE '%legal%';

UPDATE public.profiles 
SET 
    role = 'Officer'::public.app_role_enum,
    full_name = 'Inspector Rajesh Sharma',
    designation = 'Senior Inspector',
    department = 'Cybercrime Investigation Division'
WHERE LOWER(email) LIKE '%officer%' OR LOWER(email) LIKE '%investigator%';


