<!--
SYNC IMPACT REPORT
==================
Version Change: 1.0.0 → 1.1.0
Bump Rationale: MINOR - Material expansion and reorganization of existing principles with
                enhanced focus on code quality, testing standards, user experience consistency,
                and performance requirements as requested by user.

Modified Principles:
- Principle V "Reliability & Observability" expanded with performance requirements
- Code Quality section enhanced with specific standards
- Testing Requirements elevated to Core Principles section
- User Experience consistency formalized as principle

Added Sections:
- New Principle VI: Testing Standards (NON-NEGOTIABLE)
- New Principle VII: User Experience Consistency
- Enhanced Performance Constraints with specific SLOs

Removed Sections:
- None (purely additive changes)

Templates Requiring Updates:
- ✅ plan-template.md: Constitution Check section aligns with new principles
- ✅ spec-template.md: User scenarios align with UX consistency requirements
- ✅ tasks-template.md: Testing phase structure aligns with new testing standards
- ⚠️  checklist-template.md: May need code quality and test coverage checkpoints
- ⚠️  agent-file-template.md: Should verify alignment with expanded principles

Follow-up TODOs:
- Review checklist-template.md to add code quality verification steps
- Consider adding performance benchmark tasks to tasks-template.md
-->

# Exegol MCP Client Constitution

## Core Principles

### I. MCP Protocol Compliance
All features MUST strictly adhere to the Model Context Protocol specification:
- Implement standard MCP server interfaces (resources, tools, prompts)
- Support MCP transport mechanisms (stdio as primary, SSE for future consideration)
- Follow MCP JSON-RPC 2.0 message format exactly
- Provide clear capability advertisement via initialization handshake
- Version all MCP capabilities and maintain backward compatibility

**Rationale**: Protocol compliance ensures interoperability with all MCP clients and future-proofs
the implementation as the MCP specification evolves.

### II. Exegol Container Integration
Seamless integration with Exegol containers is mandatory:
- Support all Exegol CLI commands (start, stop, exec, list, info, remove)
- Maintain container state awareness and health monitoring
- Handle multiple container instances concurrently
- Preserve Exegol's security sandbox model without privilege escalation
- Detect and report Exegol version compatibility

**Rationale**: The MCP server's value derives from reliable Exegol integration. Container
operations must be transparent, safe, and predictable.

### III. Security-First Design (NON-NEGOTIABLE)
Given the penetration testing context, security is paramount:
- NEVER expose privileged container access without explicit authorization context
- Sanitize ALL command inputs to prevent command injection attacks
- Implement least-privilege principle for container operations
- Audit ALL executed commands with comprehensive structured logging
- Validate container isolation before command execution
- Fail closed on ambiguous security contexts

**Rationale**: Penetration testing tools operate in high-risk environments. A compromised
MCP server could escalate to host compromise. Security cannot be retrofitted.

**Enforcement**:
- Automated security linting (Bandit, semgrep) in CI
- Manual security review for all container interaction code
- Input validation unit tests required for all MCP tool handlers

### IV. Developer Experience
Optimize for both human operators and AI agent consumers:
- Provide intuitive tool names following MCP conventions
- Return structured JSON responses with human-readable error messages
- Include detailed error messages with actionable remediation steps
- Support both interactive and automated workflows
- Maintain comprehensive documentation in MCP prompt resources
- Design tool schemas that guide correct usage (descriptive parameter names, clear types)

**Rationale**: MCP servers are consumed by AI agents that benefit from clear, consistent
interfaces. Poor DX leads to agent confusion and error loops.

### V. Reliability & Observability
Ensure robust operation in production pentesting environments:
- Implement graceful error handling for container failures (network, permissions, missing Exegol)
- Provide detailed structured logging for all MCP interactions (debug, info, warn, error levels)
- Support configurable timeout settings for long-running commands
- Include health checks and connectivity diagnostics tools
- Version all MCP tools and track compatibility matrix
- Emit metrics for operation latency, error rates, and resource usage

**Rationale**: Pentesting workflows cannot tolerate silent failures or opaque errors.
Observability enables rapid debugging and operational confidence.

**Performance SLOs** (Service Level Objectives):
- MCP server initialization: < 2 seconds (p95)
- MCP tool invocation overhead: < 100ms (p95)
- Container command execution: < 500ms for simple commands, < 30s for complex (configurable)
- Concurrent container operations: Support ≥ 5 simultaneous operations without degradation
- Memory footprint: < 200MB for idle server, < 1GB under load

### VI. Testing Standards (NON-NEGOTIABLE)
Testing is mandatory and enforced at multiple levels:

**Unit Tests** (REQUIRED for all code):
- All MCP tool handlers MUST have unit tests with mocked Exegol interactions
- All command builders and parsers MUST have unit tests
- All input validators MUST have unit tests covering injection vectors
- Minimum coverage: 80% line coverage, 70% branch coverage

**Integration Tests** (REQUIRED for core functionality):
- Real Exegol container interactions (start, exec, stop lifecycle)
- MCP protocol handshake and capability negotiation
- Multi-container scenarios
- Error condition handling (container not found, command timeout, network failure)

**Security Tests** (REQUIRED):
- Input validation tests (SQL injection, command injection, path traversal attempts)
- Privilege escalation prevention tests
- Container isolation verification tests

**Contract Tests** (RECOMMENDED):
- MCP protocol compliance tests using official test suite
- Exegol CLI compatibility tests across versions

**Testing Workflow**:
1. Write tests FIRST (Test-Driven Development encouraged)
2. Ensure tests FAIL before implementation
3. Implement feature to pass tests
4. Add edge case tests
5. Verify coverage thresholds met

**Rationale**: Pentesting tools require extreme reliability. Untested code is unshippable.
The testing pyramid prevents regression and documents expected behavior.

### VII. User Experience Consistency
Maintain consistent patterns across all MCP tools and resources:

**Tool Naming** (MUST follow conventions):
- Action-first verbs: `exegol_start`, `exegol_exec`, `exegol_list`
- Descriptive but concise: max 3 words, snake_case
- Namespace all tools with `exegol_` prefix

**Parameter Design** (MUST be predictable):
- Use consistent parameter names across tools (`container_name`, not `name`/`container`/`id`)
- Required vs optional parameters clearly documented in schema
- Default values align with Exegol CLI defaults
- Enum parameters for constrained choices (e.g., container states)

**Response Formats** (MUST be structured):
- JSON responses with consistent top-level keys: `success`, `data`, `error`, `metadata`
- Error responses include: `error_code`, `message`, `details`, `remediation`
- Include human-readable messages alongside structured data
- Timestamps in ISO 8601 format
- Container references always include: `name`, `id`, `status`

**Error Handling** (MUST be actionable):
- Clear error categories (validation, runtime, security, exegol)
- Specific error codes (e.g., `EXEGOL_NOT_FOUND`, `CONTAINER_NOT_RUNNING`)
- Remediation suggestions (e.g., "Run `exegol start <name>` to start container")
- Context preservation in error messages (which container, which command)

**Rationale**: AI agents perform best with predictable interfaces. Inconsistency leads to
hallucinated tool usage and fragile agent workflows. Human operators benefit from patterns.

## Technical Standards

### Technology Stack
- **Language**: Python 3.10+ (required for Exegol compatibility and modern async/await)
- **MCP Framework**: Official Anthropic MCP Python SDK (`mcp` package)
- **Exegol Integration**: Subprocess calls to Exegol CLI + Docker SDK for Python (optional, for advanced features)
- **Transport**: stdio (primary, required), SSE (optional, future)
- **Testing**: pytest with pytest-asyncio, pytest-cov, pytest-mock
- **Type Checking**: mypy in strict mode
- **Linting**: ruff (replaces flake8, black, isort)
- **Security**: bandit for security linting, semgrep for pattern-based checks

**Constraints**:
- No optional dependencies for core functionality (Exegol CLI is only external dependency)
- Minimize transitive dependencies to reduce supply chain risk
- Pin all dependencies with hash verification in production

### Code Quality Standards

**Type Safety** (REQUIRED):
- Type hints for all function signatures (parameters and returns)
- Type hints for all class attributes
- Use `typing` module generics (List, Dict, Optional) over built-ins for Python < 3.9 compatibility
- Mypy strict mode compliance (no `Any` types without justification)

**Complexity Limits** (ENFORCED):
- Maximum cyclomatic complexity: 10 per function (lower threshold for stricter quality)
- Maximum function length: 50 lines (excluding docstrings)
- Maximum class length: 300 lines
- Maximum module length: 500 lines

**Code Style** (AUTOMATED):
- Ruff formatting (opinionated, no configuration needed)
- Import sorting: standard library, third-party, local (automated by ruff)
- Line length: 100 characters (balance readability and screen usage)
- Docstrings: Google style for all public functions, classes, modules

**Documentation Requirements**:
- All public APIs MUST have docstrings with:
  - Brief description
  - Args section with types and descriptions
  - Returns section with type and description
  - Raises section for expected exceptions
  - Examples section for complex functions
- Internal functions SHOULD have docstrings
- Complex algorithms MUST have inline comments explaining approach

**Async/Await Discipline**:
- All I/O operations MUST be async (subprocess, file system, network)
- Use `asyncio.gather` for concurrent operations
- Avoid blocking calls in async functions
- Use `asyncio.timeout` for all external operations

**Error Handling**:
- Use specific exception types (create custom exceptions for domain errors)
- Never use bare `except:` clauses
- Log exceptions with context before re-raising
- Convert external exceptions to domain exceptions at boundaries

### Performance Constraints

**Latency Requirements** (p95 percentiles):
- MCP initialization: < 2 seconds (includes Exegol detection)
- MCP tool invocation overhead: < 100ms (parsing, validation, dispatch)
- Container list operation: < 1 second
- Container start operation: < 10 seconds (Exegol dependent)
- Container exec operation: < 500ms for command < 1MB output
- Large output streaming: > 10 MB/s throughput

**Concurrency Requirements**:
- Support ≥ 5 concurrent container operations without blocking
- Use asyncio for I/O concurrency (not threads)
- Queue long-running operations to prevent resource exhaustion
- Implement backpressure for streaming responses

**Resource Constraints**:
- Idle memory: < 100MB
- Active memory (5 concurrent ops): < 500MB
- No memory leaks (verify with long-running stress tests)
- CPU: < 5% when idle, < 50% under load

**Scalability**:
- Linear performance degradation with container count (1-100 containers)
- Efficient caching of container state (invalidate on operations)
- Avoid O(n²) algorithms in container operations

## Development Workflow

### Implementation Cycle

1. **Design**: Define MCP tools/resources with clear JSON schemas
   - Document tool purpose, parameters, return types
   - Consider AI agent usage patterns
   - Review against UX consistency principles

2. **Test**: Write comprehensive tests BEFORE implementation
   - Unit tests for handlers (mocked Exegol)
   - Integration tests for real Exegol interactions (mark with `@pytest.mark.integration`)
   - Security tests for input validation
   - Verify tests FAIL (red phase)

3. **Implement**: Build MCP server with proper error handling
   - Follow type safety and code quality standards
   - Use async/await for all I/O
   - Add docstrings and inline comments
   - Verify tests PASS (green phase)

4. **Validate**: Test with real Exegol containers and MCP clients
   - Manual testing with Exegol CLI interop
   - Claude Desktop or other MCP client testing
   - Performance validation against SLOs
   - Security validation (input fuzzing)

5. **Refactor**: Optimize and clean up (refactor phase)
   - Check complexity metrics
   - Run linters and type checker
   - Update documentation
   - Code review

6. **Document**: Update tool descriptions and usage examples
   - Update MCP prompt resources
   - Add examples to README
   - Document breaking changes in CHANGELOG

### Testing Requirements

**Test Organization**:
```
tests/
├── unit/                # Fast, isolated tests (mocked dependencies)
│   ├── test_handlers.py
│   ├── test_validators.py
│   └── test_parsers.py
├── integration/         # Real Exegol interactions (require Docker)
│   ├── test_lifecycle.py
│   └── test_commands.py
├── security/            # Security-specific tests
│   └── test_injection.py
└── contract/            # MCP protocol compliance (optional)
    └── test_mcp_spec.py
```

**Test Execution**:
- Unit tests: Run on every commit (< 10 seconds total)
- Integration tests: Run on PR (< 2 minutes total, requires Docker)
- Security tests: Run on PR and scheduled nightly
- Contract tests: Run on MCP SDK version updates

**Test Quality Standards**:
- Minimum 80% line coverage (unit + integration combined)
- All critical paths 100% covered (security, container lifecycle)
- No flaky tests (if test fails 1% of time, fix or remove)
- Tests MUST be deterministic (no sleeps, use mocks for time)

**Continuous Integration**:
- Run unit tests + linting on every commit
- Run full test suite + type checking on PR
- Block merge if coverage drops below threshold
- Automated security scanning (Bandit, dependency audit)

### Review Criteria

All pull requests MUST pass these gates:

**Automated Checks** (blocking):
- [ ] All tests pass (unit, integration, security)
- [ ] Code coverage ≥ 80% (lines), ≥ 70% (branches)
- [ ] Mypy strict mode passes (no type errors)
- [ ] Ruff linting passes (no style violations)
- [ ] Bandit security scan passes (no high/medium issues)
- [ ] Complexity limits met (cyclomatic complexity ≤ 10)

**Manual Review** (blocking):
- [ ] MCP protocol compliance verified (correct JSON-RPC, schema adherence)
- [ ] Security audit passed for container interactions (no injection vectors)
- [ ] Documentation complete (docstrings, README updates, examples)
- [ ] UX consistency verified (tool naming, parameter conventions, error formats)
- [ ] Performance SLOs validated (if performance-critical code changed)

**Semantic Versioning**:
- MAJOR: Breaking changes to MCP tool signatures or behavior
- MINOR: New MCP tools, new optional parameters, performance improvements
- PATCH: Bug fixes, documentation, internal refactoring

**Breaking Changes**:
- Require explicit approval from project maintainers
- Document migration path in CHANGELOG
- Deprecate before removal (2 minor version grace period if feasible)
- Provide compatibility shims if backward compatibility possible

## Governance

This constitution defines the architectural, security, and quality standards for the Exegol MCP
client. All implementations MUST comply with these principles.

**Constitutional Authority**:
- This document supersedes informal practices and undocumented preferences
- When constitution conflicts with convenience, constitution wins
- Exceptions require documented justification and maintainer approval

**Amendments** require:
1. **Documented rationale**: Why is change needed? What problem does it solve?
2. **Impact assessment**: Which existing code/tests/docs affected?
3. **Migration plan**: How will existing implementations adapt?
4. **Version bump**: Follow semantic versioning (MAJOR/MINOR/PATCH)
5. **Approval**: Project maintainers must review and approve
6. **Template sync**: Update all dependent templates in `.specify/templates/`

**Enforcement**:
- All pull requests MUST reference constitution compliance in description
- Automated CI checks enforce code quality and testing standards
- Manual code review verifies security and UX consistency
- Security audits scheduled quarterly for container interaction code
- MCP protocol validation in CI pipeline using official test suite

**Complexity Justification**:
If code violates complexity limits or principles, PR description MUST include:
- Specific principle violated
- Why violation is necessary (technical constraint, external dependency limitation)
- What simpler alternatives were considered and why rejected
- Plan to remediate in future (or justification why permanent exception acceptable)

**Constitution Maintenance**:
- Review annually or after major Exegol/MCP version changes
- Track amendments in Sync Impact Report (HTML comment at top of file)
- Maintain version history in git blame (no squashing constitution changes)

**Conflict Resolution**:
When principles conflict (e.g., security vs performance):
1. Security-First Design (Principle III) always wins
2. Testing Standards (Principle VI) cannot be compromised
3. Performance can be traded for security/correctness
4. User Experience consistency can be sacrificed only for security

**Version**: 1.1.0 | **Ratified**: 2025-12-10 | **Last Amended**: 2025-12-10
