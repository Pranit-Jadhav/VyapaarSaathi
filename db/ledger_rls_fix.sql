-- VyapaarSaathi: ledger RLS unblock script (local/dev)
--
-- Why this is needed:
-- - The backend is currently writing with SUPABASE_KEY.
-- - If that key is anon and RLS is enabled on ledger, inserts fail with code 42501.
--
-- Recommended in production:
-- - Use SUPABASE_SERVICE_ROLE_KEY in backend .env instead of broad anon policies.
--
-- This script creates minimal anon policies so local dev can continue.

ALTER TABLE public.ledger ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ledger_anon_select ON public.ledger;
DROP POLICY IF EXISTS ledger_anon_insert ON public.ledger;

CREATE POLICY ledger_anon_select
ON public.ledger
FOR SELECT
TO anon, authenticated
USING (true);

CREATE POLICY ledger_anon_insert
ON public.ledger
FOR INSERT
TO anon, authenticated
WITH CHECK (true);
