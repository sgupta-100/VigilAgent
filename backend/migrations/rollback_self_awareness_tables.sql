-- ============================================================================
-- SELF-AWARE AGENTS DATABASE ROLLBACK
-- ============================================================================
-- This script safely removes all self-awareness tables and indexes from the
-- database. Use this script to rollback the self-awareness migration if needed.
--
-- WARNING: This will permanently delete all self-awareness data including:
--   - Agent proficiency scores
--   - Performance metrics
--   - Decision logs
--   - Adaptation history
--
-- Backup your data before running this script!
-- ============================================================================

BEGIN;

-- ============================================================================
-- BACKUP VERIFICATION
-- ============================================================================

DO $$
DECLARE
    proficiency_count INTEGER;
    performance_count INTEGER;
    decisions_count INTEGER;
    adaptations_count INTEGER;
BEGIN
    -- Count records in each table
    SELECT COUNT(*) INTO proficiency_count FROM agent_proficiency;
    SELECT COUNT(*) INTO performance_count FROM agent_performance;
    SELECT COUNT(*) INTO decisions_count FROM agent_decisions;
    SELECT COUNT(*) INTO adaptations_count FROM agent_adaptations;
    
    RAISE NOTICE 'Records to be deleted:';
    RAISE NOTICE '  - agent_proficiency: % records', proficiency_count;
    RAISE NOTICE '  - agent_performance: % records', performance_count;
    RAISE NOTICE '  - agent_decisions: % records', decisions_count;
    RAISE NOTICE '  - agent_adaptations: % records', adaptations_count;
    RAISE NOTICE 'Total: % records will be permanently deleted', 
        proficiency_count + performance_count + decisions_count + adaptations_count;
END $$;

-- ============================================================================
-- DROP TABLES (CASCADE to remove dependent objects)
-- ============================================================================

-- Drop agent_adaptations table
DROP TABLE IF EXISTS agent_adaptations CASCADE;
RAISE NOTICE 'Dropped table: agent_adaptations';

-- Drop agent_decisions table
DROP TABLE IF EXISTS agent_decisions CASCADE;
RAISE NOTICE 'Dropped table: agent_decisions';

-- Drop agent_performance table
DROP TABLE IF EXISTS agent_performance CASCADE;
RAISE NOTICE 'Dropped table: agent_performance';

-- Drop agent_proficiency table
DROP TABLE IF EXISTS agent_proficiency CASCADE;
RAISE NOTICE 'Dropped table: agent_proficiency';

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    table_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO table_count
    FROM information_schema.tables
    WHERE table_schema = 'public'
    AND table_name IN ('agent_proficiency', 'agent_performance', 'agent_decisions', 'agent_adaptations');
    
    IF table_count = 0 THEN
        RAISE NOTICE 'SUCCESS: All self-awareness tables removed successfully';
    ELSE
        RAISE EXCEPTION 'FAILED: Expected 0 tables, found %', table_count;
    END IF;
END $$;

COMMIT;

-- ============================================================================
-- ROLLBACK COMPLETE
-- ============================================================================
-- All self-awareness tables have been removed from the database.
-- The system will now operate without self-awareness capabilities.
--
-- To re-enable self-awareness:
--   1. Run: add_self_awareness_tables.sql
--   2. Configure feature flags
--   3. Restart agents
-- ============================================================================
