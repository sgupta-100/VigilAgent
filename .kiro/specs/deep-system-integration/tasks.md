# Implementation Plan: Deep System Integration (HARDENED)

## Overview

This implementation plan integrates the Agent Evolution System with OpenClaw browser automation using production-grade patterns: dependency injection, circuit breakers, event batching, distributed locking, feature flags, and comprehensive testing.

**Key Improvements**:
- Dependency injection (no god objects)
- Circuit breakers for failure isolation
- Event batching to prevent storms
- Distributed locking for race conditions
- Feature flags for gradual rollout
- Property-based testing
- Chaos engineering tests
- Comprehensive observability

## Tasks

- [x] 1. Foundation Infrastructure
  - [x] 1.1 Set up feature flags system
    - Create FeatureFlags dataclass
    - Add environment variable loading
    - Add gradual rollout logic (percentage-based)
    - _Requirements: Backward Compatibility_
  
  - [x] 1.2 Set up OpenTelemetry tracing
    - Configure tracer
    - Add span creation helpers
    - Integrate with Jaeger/Zipkin
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_
  
  - [x] 1.3 Set up Redis for distributed locking
    - Configure Redis client
    - Add connection pooling
    - Add health checks
    - _Requirements: 13.1, 13.2_
  
  - [x] 1.4 Create test infrastructure
    - Set up testcontainers (Redis, Postgres)
    - Create test fixtures
    - Add integration test harness
    - _Requirements: Testing_
  
  - [x] 1.5 Implement IntegrationCoordinator (with feature flags OFF)
    - Create with dependency injection
    - Add circuit breakers
    - Add event batching
    - Add concurrency control (semaphore)
    - Add metrics tracking
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_
  
  - [x]* 1.6 Write unit tests for IntegrationCoordinator
    - Test initialization
    - Test event routing
    - Test circuit breaker behavior
    - Test batch processing
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_

- [x] 2. Checkpoint - Foundation Complete
  - Verify all existing tests pass
  - Verify feature flags work
  - Verify tracing visible
  - Verify integration tests run in CI

- [x] 3. Browser Learning Engine Extension (with idempotency)
  - [x] 3.1 Implement BrowserLearningExtension class
    - Add Redis client dependency
    - Add idempotency key generation
    - Add distributed locking (acquire/release)
    - Add learning cache
    - _Requirements: 1.1, 2.1, 2.2, 2.3, 2.4_
  
  - [x] 3.2 Implement learn_from_browser_vulnerability method
    - Generate idempotency key from vuln data
    - Acquire distributed lock
    - Check cache for duplicates
    - Extract browser-specific pattern
    - Tag with browser context
    - Store with execution requirements
    - Publish SKILL_EXTRACTED event
    - _Requirements: 1.1, 1.2, 1.3, 1.5_
  
  - [x]* 3.3 Write property test for idempotency
    - **Property 1: Browser Skill Creation and Tagging**
    - **Property: Idempotency of Vulnerability Learning**
    - Use Hypothesis to generate random vulnerabilities
    - Test learning same vuln twice returns False
    - Test no duplicate skills created
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.5**
  
  - [x] 3.4 Implement learn_browser_workflow method
    - Get existing workflow stats from Redis
    - Update stats incrementally
    - Calculate success rate
    - Promote to skill if threshold reached
    - _Requirements: 16.1, 16.6_
  
  - [x] 3.5 Implement get_browser_recommendations method
    - Add LRU cache decorator
    - Query patterns from database
    - Rank by confidence and success rate
    - Return workflows, payloads, framework-specific
    - _Requirements: 2.5, 2.6_
  
  - [x]* 3.6 Write property test for recommendations
    - **Property 5: Browser-Based Recommendations**
    - Test recommendations are subset of stored patterns
    - Test ranking is correct
    - **Validates: Requirements 2.5, 2.6**
  
  - [x] 3.7 Implement learn_framework_pattern method
    - Deduplicate routes
    - Get existing framework routes from Redis
    - Add only new routes
    - Extract route patterns
    - Store patterns for matching
    - _Requirements: 2.1_
  
  - [x] 3.8 Enable browser learning for 10% of scans
    - Set ENABLE_BROWSER_LEARNING=true
    - Set BROWSER_LEARNING_ROLLOUT_PCT=10
    - Monitor metrics for 1 week
    - _Requirements: Gradual Rollout_

- [x] 4. Checkpoint - Learning Engine Complete
  - Verify property tests pass
  - Verify no duplicate skills created
  - Verify cache hit rate > 50%
  - Verify 10% rollout successful

- [x] 5. Skill Library Extension (with indexing)
  - [x] 5.1 Create BrowserSkill dataclass
    - Add execution_context field
    - Add browser_requirements field
    - Add workflow_steps field
    - Add evidence_requirements field
    - Add version field (semantic versioning)
    - Add deprecated field
    - Add required_capabilities field
    - _Requirements: 1.5, 4.1, 4.2_
  
  - [x] 5.2 Implement BrowserSkillLibraryExtension class
    - Create capability index (Dict[str, Set[str]])
    - Create context index (Dict[str, Set[str]])
    - Create framework index (Dict[str, Set[str]])
    - Create version tracking (Dict[str, List[str]])
    - _Requirements: 4.1, 4.2_
  
  - [x] 5.3 Implement add_browser_skill method
    - Validate version format (semver)
    - Check for duplicates
    - Store skill
    - Update all indexes
    - Track version
    - Tag with "browser_automation"
    - _Requirements: 1.2, 1.3, 1.5_
  
  - [x]* 5.4 Write property test for skill storage
    - **Property 3: High-Confidence Skill Distribution**
    - **Property 10: Unified Skill Storage**
    - Generate random skills with Hypothesis
    - Test all stored skills are retrievable
    - Test no duplicates created
    - **Validates: Requirements 1.6, 4.1, 4.2**
  
  - [x] 5.5 Implement search_browser_skills method
    - Use indexes for O(1) lookups
    - Filter by context (if provided)
    - Filter by framework (if provided)
    - Filter by capabilities (subset check)
    - Skip deprecated skills
    - Sort by success rate and usage
    - _Requirements: 4.3_
  
  - [x]* 5.6 Write property test for capability filtering
    - **Property 11: Capability-Based Skill Filtering**
    - Test filtered skills match agent capabilities
    - Test results are subset of all skills
    - Test deprecated skills excluded
    - **Validates: Requirements 4.3**
  
  - [x] 5.7 Implement compose_workflows method
    - Validate all are workflows
    - Validate compatibility
    - Merge workflow steps
    - Merge success conditions
    - Merge browser requirements
    - Create composed skill
    - _Requirements: 16.4_
  
  - [x]* 5.8 Write property test for workflow composition
    - **Property 55: Workflow Composition**
    - Test composed workflow contains all steps
    - Test composed requirements are union
    - **Validates: Requirements 16.4**
  
  - [x] 5.9 Implement deprecate_skill method
    - Mark skill as deprecated
    - Set deprecation reason
    - Set migration path
    - Log deprecation
    - _Requirements: 4.6_
  
  - [x] 5.10 Migrate existing skills to new format
    - Export existing skills
    - Add version numbers
    - Add capability requirements
    - Re-import with indexes
    - Verify migration
    - _Requirements: 4.1, 4.2_
  
  - [x] 5.11 Enable skill library for 25% of scans
    - Set rollout to 25%
    - Monitor skill search latency
    - Monitor index performance
    - _Requirements: Gradual Rollout_

- [x] 6. Checkpoint - Skill Library Complete
  - Verify property tests pass
  - Verify skill search < 10ms (p99)
  - Verify all skills migrated
  - Verify 25% rollout successful

- [x] 7. Health Monitor Extension (browser metrics)
  - [x] 7.1 Create BrowserHealthMetrics dataclass
    - Add active_contexts field
    - Add context_memory_mb field
    - Add page_load_time_ms field
    - Add screenshot_time_ms field
    - Add browser_error_rate field
    - _Requirements: 5.1, 6.2, 6.3, 6.4_
  
  - [x] 7.2 Implement report_browser_metrics method
    - Store browser metrics
    - Calculate browser health score
    - Alert if browser operations impact system
    - _Requirements: 6.2, 6.3, 6.6_
  
  - [x]* 7.3 Write property test for browser health monitoring
    - **Property 15: Browser Metric Tracking**
    - **Property 21: Universal Health Monitoring**
    - Test metrics are tracked correctly
    - Test health score calculation
    - **Validates: Requirements 5.1, 6.1, 6.2, 6.3, 6.4**
  
  - [x] 7.4 Implement get_browser_health method
    - Return browser metrics
    - Include context count and memory
    - _Requirements: 6.2, 6.4_
  
  - [x] 7.5 Implement calculate_browser_health_score method
    - Factor in context count
    - Factor in memory usage
    - Factor in page load times
    - Factor in error rate
    - _Requirements: 6.3_
  
  - [x]* 7.6 Write property test for health score calculation
    - **Property 22: Browser Health Impact Alerts**
    - Test alerts fire when health drops
    - Test score calculation is consistent
    - **Validates: Requirements 6.6**
  
  - [x] 7.7 Add browser metrics to dashboard
    - Create browser health panel
    - Add real-time context count
    - Add memory usage graph
    - Add error rate chart
    - _Requirements: 15.1, 15.4_
  
  - [x] 7.8 Enable health monitoring for 50% of scans
    - Set rollout to 50%
    - Monitor dashboard
    - Verify alerts work
    - _Requirements: Gradual Rollout_

- [x] 8. Checkpoint - Health Monitor Complete
  - Verify property tests pass
  - Verify metrics visible in dashboard
  - Verify alerts fire correctly
  - Verify 50% rollout successful

- [x] 9. Self-Healing Engine Extension (browser recovery)
  - [x] 9.1 Implement heal_browser_crash method
    - Detect crash via Health Monitor
    - Restart browser context
    - Restore session state
    - Apply exponential backoff
    - _Requirements: 3.1, 3.2, 3.5_
  
  - [x]* 9.2 Write property test for browser crash recovery
    - **Property 6: Browser Crash Detection and Recovery**
    - Test crash is detected
    - Test context is restarted
    - Test session state restored
    - **Validates: Requirements 3.1, 3.2, 3.5**
  
  - [x] 9.3 Implement heal_browser_memory method
    - Close idle contexts
    - Clear context pool
    - Trigger garbage collection
    - _Requirements: 3.3, 5.3_
  
  - [x]* 9.4 Write property test for memory management
    - **Property 7: Browser Memory Management**
    - **Property 17: Memory-Triggered Cleanup**
    - Test idle contexts are closed
    - Test memory is freed
    - **Validates: Requirements 3.3, 5.3**
  
  - [x] 9.5 Implement adapt_browser_strategy method
    - Switch to stealth mode on failures
    - Reduce concurrency
    - Fall back to HTTP
    - _Requirements: 3.4_
  
  - [x]* 9.6 Write property test for strategy adaptation
    - **Property 8: Browser Strategy Adaptation**
    - Test strategy changes after repeated failures
    - Test fallback to HTTP works
    - **Validates: Requirements 3.4**
  
  - [x] 9.7 Implement browser circuit breaker
    - Track browser target failures
    - Open circuit after threshold
    - Close circuit after timeout
    - _Requirements: 3.6_
  
  - [x]* 9.8 Write property test for browser circuit breaker
    - **Property 9: Browser Circuit Breaker**
    - Test circuit opens after failures
    - Test circuit closes after timeout
    - **Validates: Requirements 3.6**
  
  - [x]* 9.9 Write chaos test for resilience
    - **Chaos Test: Coordinator Survives Learning Engine Crash**
    - Inject 50% failure rate into learning engine
    - Send 100 events
    - Verify coordinator still healthy
    - Verify failure rate < 60%
    - **Validates: Resilience**
  
  - [x] 9.10 Enable self-healing for 75% of scans
    - Set rollout to 75%
    - Monitor recovery success rate
    - Monitor circuit breaker trips
    - _Requirements: Gradual Rollout_

- [x] 10. Checkpoint - Self-Healing Complete
  - Verify property tests pass
  - Verify chaos tests pass
  - Verify recovery rate > 95%
  - Verify 75% rollout successful

- [x] 11. Knowledge Graph Extension (HTTP-browser linking)
  - [x] 11.1 Add browser discovery node types
    - Add BrowserEndpoint node type
    - Add JavaScriptRoute node type
    - Add WebSocketConnection node type
    - _Requirements: 7.1, 7.2_
  
  - [x] 11.2 Implement add_browser_discovery method
    - Create node with source="browser_recon"
    - Link to HTTP equivalent if exists
    - Store discovery metadata
    - _Requirements: 7.1, 7.2, 7.3_
  
  - [x]* 11.3 Write property test for discovery source tagging
    - **Property 23: Discovery Source Tagging**
    - Test source is tagged correctly
    - Test metadata is stored
    - **Validates: Requirements 7.1, 7.2, 7.5**
  
  - [x] 11.4 Implement link_http_browser_endpoints method
    - Create HTTP_EQUIVALENT relationship
    - Merge metadata
    - Deduplicate discoveries
    - _Requirements: 7.3, 7.4_
  
  - [x]* 11.5 Write property test for endpoint linking
    - **Property 24: HTTP-Browser Endpoint Linking**
    - Test endpoints are linked correctly
    - Test deduplication works
    - **Validates: Requirements 7.3, 7.4**
  
  - [x] 11.6 Implement get_endpoint_context method
    - Return HTTP discovery data
    - Return browser discovery data
    - Return linked endpoints
    - _Requirements: 7.6_
  
  - [x]* 11.7 Write property test for unified endpoint context
    - **Property 25: Unified Endpoint Context**
    - Test both HTTP and browser context returned
    - Test linked endpoints included
    - **Validates: Requirements 7.6**
  
  - [x] 11.8 Enable knowledge graph for 100% of scans
    - Set rollout to 100%
    - Monitor graph queries
    - Monitor deduplication rate
    - _Requirements: Gradual Rollout_

- [x] 12. Checkpoint - Knowledge Graph Complete
  - Verify property tests pass
  - Verify endpoints are linked
  - Verify deduplication works
  - Verify 100% rollout successful

- [x] 13. Cross-System Features (routing + forensics)
  - [x] 13.1 Implement IntelligentRouter class
    - Initialize with learning_engine and browser_orchestrator
    - Set up routing decision logic
    - _Requirements: 17.1, 17.2_
  
  - [x] 13.2 Implement recommend_method method
    - Query learned patterns
    - Check target characteristics
    - Return HTTP-only, browser-only, or hybrid
    - _Requirements: 17.2, 17.5_
  
  - [x]* 13.3 Write property test for method recommendation
    - **Property 59: Method Recommendation Based on Patterns**
    - Test recommendations match learned patterns
    - Test HTTP-only recommended when appropriate
    - **Validates: Requirements 17.2, 17.5**
  
  - [x] 13.4 Implement select_browser_engine method
    - Analyze task complexity
    - Check stealth requirements
    - Return PinchTab or OpenClaw
    - _Requirements: 17.3_
  
  - [x]* 13.5 Write property test for engine selection
    - **Property 60: Complexity-Based Engine Selection**
    - Test PinchTab selected for simple tasks
    - Test OpenClaw selected for complex tasks
    - **Validates: Requirements 17.3**
  
  - [x] 13.6 Implement ForensicLearningBridge class
    - Initialize with learning_engine and forensic_collector
    - Set up evidence quality metrics
    - _Requirements: 9.1, 9.2_
  
  - [x] 13.7 Implement analyze_evidence_quality method
    - Check for required evidence types
    - Calculate quality score
    - Identify gaps
    - _Requirements: 9.2_
  
  - [x]* 13.8 Write property test for evidence quality
    - **Property 32: Evidence Quality Analysis**
    - Test quality score calculation
    - Test gap identification
    - **Validates: Requirements 9.2**
  
  - [x] 13.9 Implement learn_evidence_requirements method
    - Track evidence types per vulnerability
    - Calculate value scores
    - Store requirements
    - _Requirements: 9.3_
  
  - [x]* 13.10 Write property test for evidence learning
    - **Property 33: Evidence Value Learning**
    - Test evidence requirements are learned
    - Test value scores are tracked
    - **Validates: Requirements 9.3**
  
  - [x] 13.11 Enable routing and forensics for 100%
    - Enable all features
    - Monitor routing decisions
    - Monitor evidence quality
    - _Requirements: Gradual Rollout_

- [x] 14. Checkpoint - Cross-System Features Complete
  - Verify property tests pass
  - Verify routing improves success rate
  - Verify evidence quality improves
  - Verify 100% rollout successful

- [x] 15. End-to-End Testing
  - [x]* 15.1 Write E2E test for complete integrated scan
    - Test full scan with all systems integrated
    - Test HTTP and browser agents collaborate
    - Test learning, healing, and skills all work
    - Test vulnerability → pattern → skill → distribution
    - **Validates: All Requirements**
  
  - [x]* 15.2 Write E2E test for browser crash recovery
    - Test crash → detection → healing → restoration
    - Verify self-healing works end-to-end
    - **Validates: Requirements 3.1, 3.2, 3.5**
  
  - [x]* 15.3 Write E2E test for cross-system learning
    - Test HTTP vuln → browser verification → hybrid skill
    - Verify cross-method learning works
    - **Validates: Requirements 8.1, 8.2, 8.3, 8.6**
  
  - [x]* 15.4 Write chaos test for event storm handling
    - Send 1000 events rapidly
    - Verify system doesn't crash
    - Verify batching works
    - **Validates: Event Batching**

- [x] 16. Final Checkpoint - All Tests Pass
  - Verify all property tests pass (80 properties)
  - Verify all integration tests pass
  - Verify all E2E tests pass
  - Verify all chaos tests pass
  - Verify performance within 10% of baseline

- [x] 17. Documentation and Deployment
  - [x] 17.1 Update API documentation
    - Document new endpoints
    - Document new event types
    - Document integration configuration
  
  - [x] 17.2 Update architecture documentation
    - Document integration architecture
    - Document event flows
    - Document data models
  
  - [x] 17.3 Create operational runbooks
    - Daily health check procedures
    - Troubleshooting guides
    - Rollback procedures
    - Skill library maintenance
  
  - [x] 17.4 Create monitoring dashboards
    - Integration health dashboard
    - Learning performance dashboard
    - Skill library dashboard
    - Browser health dashboard
  
  - [x] 17.5 Configure alerting rules
    - High failure rate alert
    - Circuit breaker alert
    - Slow skill search alert
    - Browser memory leak alert
  
  - [x] 17.6 Final deployment to production
    - Deploy with feature flags OFF
    - Enable for 1% (canary)
    - Monitor for 1 week
    - Gradually increase to 100%

## Notes

- Tasks marked with `*` are property-based or chaos tests
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Chaos tests validate resilience under failure

## Task Dependency Graph

```json
{
  "waves": [
    { "wave": 1, "tasks": ["1. Foundation Infrastructure"] },
    { "wave": 2, "tasks": ["2. Checkpoint - Foundation Complete"] },
    { "wave": 3, "tasks": ["3. Browser Learning Engine Extension (with idempotency)"] },
    { "wave": 4, "tasks": ["4. Checkpoint - Learning Engine Complete"] },
    { "wave": 5, "tasks": ["5. Skill Library Extension (with indexing)"] },
    { "wave": 6, "tasks": ["6. Checkpoint - Skill Library Complete"] },
    { "wave": 7, "tasks": ["7. Health Monitor Extension (browser metrics)"] },
    { "wave": 8, "tasks": ["8. Checkpoint - Health Monitor Complete"] },
    { "wave": 9, "tasks": ["9. Self-Healing Engine Extension (browser recovery)"] },
    { "wave": 10, "tasks": ["10. Checkpoint - Self-Healing Complete"] },
    { "wave": 11, "tasks": ["11. Knowledge Graph Extension (HTTP-browser linking)"] },
    { "wave": 12, "tasks": ["12. Checkpoint - Knowledge Graph Complete"] },
    { "wave": 13, "tasks": ["13. Cross-System Features (routing + forensics)"] },
    { "wave": 14, "tasks": ["14. Checkpoint - Cross-System Features Complete"] },
    { "wave": 15, "tasks": ["15. End-to-End Testing"] },
    { "wave": 16, "tasks": ["16. Final Checkpoint - All Tests Pass"] },
    { "wave": 17, "tasks": ["17. Documentation and Deployment"] }
  ]
}
```

