-- ============================================================================
-- SELF-AWARE AGENTS DATABASE MIGRATION
-- ============================================================================
-- This migration adds tables for self-awareness capabilities to the Vulagent
-- penetration testing system. These tables enable agents to track their own
-- performance, understand capabilities, adapt strategies, log decisions,
-- and coordinate intelligently.
--
-- Tables Created:
--   1. agent_proficiency - Skill proficiency scores per agent
--   2. agent_performance - Performance metrics and resource usage
--   3. agent_decisions - Decision rationale and confidence levels
--   4. agent_adaptations - Strategy adaptation history
--
-- Requirements: PostgreSQL 12+
-- ============================================================================

BEGIN;

-- ============================================================================
-- TABLE 1: agent_proficiency
-- Purpose: Track skill proficiency scores for each agent
-- ============================================================================

CREATE TABLE IF NOT EXISTS agent_proficiency (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(50) NOT NULL,
    skill VARCHAR(100) NOT NULL,
    proficiency_score FLOAT NOT NULL CHECK (proficiency_score >= 0 AND proficiency_score <= 1),
    last_updated TIMESTAMP NOT NULL DEFAULT NOW(),
    total_attempts INTEGER NOT NULL DEFAULT 0,
    successful_attempts INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(agent_id, skill)
);

-- Indexes for agent_proficiency
CREATE INDEX idx_agent_proficiency_agent ON agent_proficiency(agent_id);
CREATE INDEX idx_agent_proficiency_skill ON agent_proficiency(skill);
CREATE INDEX idx_agent_proficiency_score ON agent_proficiency(proficiency_score DESC);
CREATE INDEX idx_agent_proficiency_updated ON agent_proficiency(last_updated DESC);

-- ============================================================================
-- TABLE 2: agent_performance
-- Purpose: Track performance metrics and resource usage per action
-- ============================================================================

CREATE TABLE IF NOT EXISTS agent_performance (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(50) NOT NULL,
    tracking_id VARCHAR(100) NOT NULL UNIQUE,
    action_type VARCHAR(100) NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    success BOOLEAN,
    cpu_usage FLOAT,
    memory_mb FLOAT,
    api_calls INTEGER,
    error_message TEXT,
    context JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for agent_performance
CREATE INDEX idx_agent_performance_agent ON agent_performance(agent_id);
CREATE INDEX idx_agent_performance_time ON agent_performance(start_time DESC);
CREATE INDEX idx_agent_performance_action ON agent_performance(action_type);
CREATE INDEX idx_agent_performance_success ON agent_performance(success);
CREATE INDEX idx_agent_performance_tracking ON agent_performance(tracking_id);

-- ============================================================================
-- TABLE 3: agent_decisions
-- Purpose: Record decision rationale and confidence levels
-- ============================================================================

CREATE TABLE IF NOT EXISTS agent_decisions (
    id SERIAL PRIMARY KEY,
    decision_id VARCHAR(100) NOT NULL UNIQUE,
    agent_id VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    action_type VARCHAR(100) NOT NULL,
    rationale TEXT NOT NULL,
    confidence FLOAT NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    alternatives_considered JSONB,
    context JSONB,
    finding_id VARCHAR(100),
    scan_id VARCHAR(100),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for agent_decisions
CREATE INDEX idx_agent_decisions_agent ON agent_decisions(agent_id);
CREATE INDEX idx_agent_decisions_time ON agent_decisions(timestamp DESC);
CREATE INDEX idx_agent_decisions_finding ON agent_decisions(finding_id);
CREATE INDEX idx_agent_decisions_scan ON agent_decisions(scan_id);
CREATE INDEX idx_agent_decisions_action ON agent_decisions(action_type);

-- Full-text search index on rationale
CREATE INDEX idx_agent_decisions_rationale_fts ON agent_decisions 
    USING gin(to_tsvector('english', rationale));

-- ============================================================================
-- TABLE 4: agent_adaptations
-- Purpose: Track strategy adaptations and their outcomes
-- ============================================================================

CREATE TABLE IF NOT EXISTS agent_adaptations (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    trigger_reason VARCHAR(100) NOT NULL,
    strategy_applied VARCHAR(100) NOT NULL,
    success BOOLEAN,
    context JSONB,
    scan_id VARCHAR(100),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for agent_adaptations
CREATE INDEX idx_agent_adaptations_agent ON agent_adaptations(agent_id);
CREATE INDEX idx_agent_adaptations_time ON agent_adaptations(timestamp DESC);
CREATE INDEX idx_agent_adaptations_strategy ON agent_adaptations(strategy_applied);
CREATE INDEX idx_agent_adaptations_scan ON agent_adaptations(scan_id);

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Verify tables were created
DO $$
DECLARE
    table_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO table_count
    FROM information_schema.tables
    WHERE table_schema = 'public'
    AND table_name IN ('agent_proficiency', 'agent_performance', 'agent_decisions', 'agent_adaptations');
    
    IF table_count = 4 THEN
        RAISE NOTICE 'SUCCESS: All 4 self-awareness tables created successfully';
    ELSE
        RAISE EXCEPTION 'FAILED: Expected 4 tables, found %', table_count;
    END IF;
END $$;

COMMIT;

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================
-- Migration completed successfully. Self-awareness tables are now available.
-- Next steps:
--   1. Run rollback script if needed: rollback_self_awareness_tables.sql
--   2. Configure feature flags in backend/core/feature_flags.py
--   3. Initialize SelfAwarenessModule in agent base class
-- ============================================================================
