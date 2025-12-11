# CLI Workflow Harness - Usage Guide

## Overview

The CLI Workflow Harness is a comprehensive testing framework that validates the entire TasksGodzilla workflow from project onboarding through discovery, specs, protocol execution, and changes. It identifies missing features, broken workflows, and areas needing fixes or new implementations.

## Quick Start

### Basic Usage

```bash
# Run smoke tests (fastest, critical path only)
python scripts/cli_workflow_harness.py --mode smoke

# Run full workflow validation
python scripts/cli_workflow_harness.py --mode full

# Run with verbose output
python scripts/cli_workflow_harness.py --mode development --verbose
```

### Prerequisites

Before running the harness, ensure your environment is properly set up:

```bash
# Bootstrap the environment
scripts/ci/bootstrap.sh

# Verify required services are running
redis-server --port 6379 &

# Set required environment variables
export TASKSGODZILLA_DB_PATH=/tmp/tasksgodzilla-test.sqlite
export TASKSGODZILLA_REDIS_URL=redis://localhost:6379/15
```

## Execution Modes

The harness supports six different execution modes, each optimized for specific use cases:

### 1. Smoke Mode (`--mode smoke`)

**Use Case**: Quick validation of critical functionality  
**Duration**: ~5 minutes  
**Components**: Essential workflow components only

```bash
python scripts/cli_workflow_harness.py --mode smoke
```

**What it tests**:
- Basic CLI functionality
- Core onboarding workflow
- Essential API endpoints
- Critical error handling

**When to use**:
- Before committing changes
- Quick regression testing
- CI pre-checks

### 2. Full Mode (`--mode full`)

**Use Case**: Comprehensive end-to-end validation  
**Duration**: ~30 minutes  
**Components**: All workflow components

```bash
python scripts/cli_workflow_harness.py --mode full --parallel
```

**What it tests**:
- Complete onboarding → discovery → protocol → spec workflow
- All CLI interfaces (interactive, command-line, TUI)
- API and worker integration
- Error conditions and edge cases
- Performance validation

**When to use**:
- Before releases
- Weekly regression testing
- Comprehensive validation after major changes

### 3. Component Mode (`--mode component`)

**Use Case**: Testing specific components in isolation  
**Duration**: Variable (5-15 minutes per component)  
**Components**: User-specified subset

```bash
# Test specific components
python scripts/cli_workflow_harness.py --mode component \
  --components onboarding discovery protocol

# Test CLI interfaces only
python scripts/cli_workflow_harness.py --mode component \
  --components cli_interface tui_interface
```

**Available components**:
- `onboarding`: Project onboarding via `scripts/onboard_repo.py`
- `discovery`: Repository analysis and documentation generation
- `protocol`: Protocol creation and execution via `scripts/protocol_pipeline.py`
- `spec`: Spec-driven development workflow
- `quality`: Quality orchestration via `scripts/quality_orchestrator.py`
- `cli_interface`: CLI command testing
- `tui_interface`: Text UI testing
- `api_integration`: API server and worker testing
- `error_conditions`: Error handling validation
- `failure_detection`: Missing feature detection

**When to use**:
- Debugging specific functionality
- Focused testing during development
- Isolating test failures

### 4. Regression Mode (`--mode regression`)

**Use Case**: Focus on previously failing scenarios  
**Duration**: ~10-15 minutes  
**Components**: Components with historical failures

```bash
python scripts/cli_workflow_harness.py --mode regression \
  --output-format json
```

**What it tests**:
- Previously identified failure patterns
- Known edge cases and error conditions
- Components with recent fixes
- Performance regression detection

**When to use**:
- After bug fixes
- Validating resolved issues
- Continuous regression monitoring

### 5. Development Mode (`--mode development`)

**Use Case**: Detailed debugging and development  
**Duration**: Variable  
**Components**: User-specified with extensive logging

```bash
python scripts/cli_workflow_harness.py --mode development \
  --verbose --log-file harness-debug.log \
  --components onboarding
```

**Features**:
- Verbose output and detailed logging
- Extended timeouts for debugging
- Detailed error traces and context
- Interactive failure analysis
- Performance profiling

**When to use**:
- Developing new harness components
- Debugging test failures
- Performance analysis
- Understanding workflow behavior

### 6. CI Mode (`--mode ci`)

**Use Case**: Automated continuous integration  
**Duration**: ~15-20 minutes  
**Components**: All components, optimized for automation

```bash
python scripts/cli_workflow_harness.py --mode ci \
  --output-format junit --output-dir ./ci-reports \
  --exit-on-failure
```

**Features**:
- Non-interactive execution
- Machine-readable output (JUnit XML, JSON)
- Parallel execution for speed
- Clear exit codes for CI systems
- Integration with existing CI scripts

**When to use**:
- GitHub Actions / GitLab CI pipelines
- Automated testing workflows
- Release validation
- Continuous monitoring

## Configuration Options

### Command-Line Arguments

```bash
python scripts/cli_workflow_harness.py [OPTIONS]

# Execution mode
--mode, -m {full,component,smoke,regression,development,ci}
                        Test execution mode (default: smoke)

# Component selection
--components, -c {onboarding,discovery,protocol,spec,quality,cli_interface,tui_interface,api_integration,error_conditions,failure_detection}
                        Specific components to test

# Configuration
--config CONFIG         Configuration file path (JSON format)

# Output options
--output-dir, -o OUTPUT_DIR
                        Output directory for reports (default: ./harness-output)
--output-format {text,json,junit,all}
                        Output format for CI systems (default: text)

# Execution options
--parallel, -p          Enable parallel test execution
--max-workers MAX_WORKERS
                        Maximum number of parallel workers (default: 4)
--timeout TIMEOUT       Test execution timeout in seconds (default: 1800)

# Logging options
--verbose, -v           Enable verbose output
--log-file LOG_FILE     Log file path for detailed logging

# Test data options
--test-data-path TEST_DATA_PATH
                        Test data directory path (default: ./tests/harness/data)

# CI-specific options
--ci                    Force CI mode (non-interactive, machine-readable output)
--exit-on-failure       Exit with non-zero code on test failures
```

### Configuration Files

You can use JSON configuration files to define reusable test configurations:

```json
{
  "mode": "component",
  "components": ["onboarding", "discovery", "cli_interface"],
  "verbose": false,
  "parallel": true,
  "timeout": 900,
  "max_workers": 4,
  "output_formats": ["text", "json"],
  "description": "Development testing configuration",
  "environments": {
    "development": {
      "verbose": true,
      "timeout": 1800,
      "components": ["onboarding", "discovery", "protocol", "spec"]
    },
    "ci": {
      "mode": "ci",
      "parallel": true,
      "max_workers": 8,
      "timeout": 1200,
      "components": []
    }
  }
}
```

Use with:
```bash
python scripts/cli_workflow_harness.py --config my-config.json
```

## Environment Setup

### Required Environment Variables

```bash
# Database configuration (choose one)
export TASKSGODZILLA_DB_URL="postgresql://user:pass@localhost/tasksgodzilla"
export TASKSGODZILLA_DB_PATH="/tmp/tasksgodzilla-test.sqlite"

# Redis configuration
export TASKSGODZILLA_REDIS_URL="redis://localhost:6379/15"

# Optional: API authentication
export TASKSGODZILLA_API_TOKEN="your-api-token"

# Optional: Codex CLI path (for discovery tests)
export CODEX_CLI_PATH="/path/to/codex"

# Optional: Enable inline worker for testing
export TASKSGODZILLA_INLINE_RQ_WORKER=true
```

### Database Setup

For SQLite (recommended for testing):
```bash
export TASKSGODZILLA_DB_PATH=/tmp/tasksgodzilla-harness.sqlite
# Database will be created automatically
```

For PostgreSQL:
```bash
# Create test database
createdb tasksgodzilla_test

# Set connection URL
export TASKSGODZILLA_DB_URL="postgresql://localhost/tasksgodzilla_test"

# Run migrations
alembic upgrade head
```

### Redis Setup

Start Redis server:
```bash
# Using default Redis installation
redis-server --port 6379 &

# Using Docker
docker run -d -p 6379:6379 redis:alpine

# Verify connection
redis-cli -p 6379 ping
```

### Service Dependencies

The harness can test with or without external services:

**With Codex** (full discovery testing):
```bash
# Install and configure Codex CLI
export CODEX_CLI_PATH="/usr/local/bin/codex"
```

**Without Codex** (graceful degradation):
- Discovery tests will run in mock mode
- Harness will report Codex unavailability
- Other components continue normally

## Common Testing Scenarios

### 1. Pre-Commit Validation

Quick validation before committing changes:

```bash
# Run smoke tests with verbose output
python scripts/cli_workflow_harness.py --mode smoke --verbose

# Check specific components you modified
python scripts/cli_workflow_harness.py --mode component \
  --components onboarding protocol --verbose
```

### 2. Feature Development Testing

Testing during feature development:

```bash
# Development mode with detailed logging
python scripts/cli_workflow_harness.py --mode development \
  --components spec quality \
  --verbose --log-file feature-testing.log

# Test with realistic data
python scripts/cli_workflow_harness.py --mode component \
  --components onboarding discovery \
  --test-data-path ./my-test-projects
```

### 3. Release Validation

Comprehensive testing before releases:

```bash
# Full validation with parallel execution
python scripts/cli_workflow_harness.py --mode full \
  --parallel --max-workers 8 \
  --output-format all --output-dir ./release-validation

# Generate comprehensive reports
python scripts/cli_workflow_harness.py --mode full \
  --output-format json \
  --exit-on-failure
```

### 4. CI Integration

Automated testing in CI pipelines:

```bash
# CI mode with JUnit output
python scripts/cli_workflow_harness.py --mode ci \
  --output-format junit --output-dir ./ci-reports \
  --parallel --exit-on-failure

# Regression testing
python scripts/cli_workflow_harness.py --mode regression \
  --output-format json --ci
```

### 5. Performance Testing

Monitoring performance and resource usage:

```bash
# Full mode with performance monitoring
python scripts/cli_workflow_harness.py --mode full \
  --parallel --verbose \
  --log-file performance.log

# Development mode for detailed profiling
python scripts/cli_workflow_harness.py --mode development \
  --components api_integration \
  --verbose --timeout 3600
```

## Understanding Test Results

### Report Formats

The harness generates reports in multiple formats:

**Text Report** (human-readable):
```
CLI Workflow Harness - Execution Summary
========================================
Execution ID: harness_20231211_143022
Mode: full
Duration: 1247.32s
Total Tests: 156
Passed: 142
Failed: 14
Success Rate: 91.0%
Peak Memory: 512.3 MB
Parallel Efficiency: 78.5%

Critical Issues: 3
  - Protocol step execution timeout (protocol)
  - Missing CLI command validation (cli_interface)
  - Discovery output parsing failure (discovery)

Top Recommendations:
  1. [FIX] Implement timeout handling in protocol execution
  2. [IMPLEMENT] Add CLI command validation framework
  3. [IMPROVE] Enhance discovery output parsing robustness
```

**JSON Report** (machine-readable):
```json
{
  "execution_id": "harness_20231211_143022",
  "mode": "full",
  "start_time": "2023-12-11T14:30:22Z",
  "end_time": "2023-12-11T15:10:49Z",
  "total_tests": 156,
  "passed_tests": 142,
  "failed_tests": 14,
  "success_rate": 91.0,
  "performance_metrics": {
    "total_duration": 1247.32,
    "peak_memory_mb": 512.3,
    "parallel_efficiency": 78.5
  },
  "missing_features": [
    {
      "feature_name": "Protocol step execution timeout",
      "component": "protocol",
      "description": "Protocol execution lacks timeout handling",
      "impact": "critical"
    }
  ],
  "recommendations": [
    {
      "priority": 1,
      "category": "fix",
      "description": "Implement timeout handling in protocol execution",
      "estimated_effort": "medium"
    }
  ]
}
```

**JUnit XML** (CI integration):
```xml
<?xml version="1.0" encoding="UTF-8"?>
<testsuites name="CLI Workflow Harness" tests="156" failures="14" time="1247.32">
  <testsuite name="onboarding" tests="23" failures="1" time="156.7">
    <testcase name="test_onboard_python_project" time="12.3"/>
    <testcase name="test_onboard_invalid_repo" time="5.1">
      <failure message="Repository validation failed">...</failure>
    </testcase>
  </testsuite>
</testsuites>
```

### Exit Codes

The harness uses standard exit codes for CI integration:

- `0`: All tests passed successfully
- `1`: Test failures detected (when `--exit-on-failure` is used)
- `2`: Configuration or environment errors
- `130`: Interrupted by user (Ctrl+C)

### Performance Metrics

The harness tracks several performance indicators:

- **Total Duration**: Complete execution time
- **Peak Memory**: Maximum memory usage during execution
- **CPU Utilization**: Average CPU usage across all cores
- **Parallel Efficiency**: Effectiveness of parallel execution (target: >70%)
- **Threshold Violations**: Performance thresholds exceeded

## Troubleshooting

### Common Issues

**1. Database Connection Errors**
```
Error: Database connection failed
```
Solution:
```bash
# Check database configuration
echo $TASKSGODZILLA_DB_PATH
echo $TASKSGODZILLA_DB_URL

# For SQLite, ensure directory exists
mkdir -p $(dirname $TASKSGODZILLA_DB_PATH)

# For PostgreSQL, verify connection
psql $TASKSGODZILLA_DB_URL -c "SELECT 1;"
```

**2. Redis Connection Errors**
```
Error: Redis connection refused
```
Solution:
```bash
# Check Redis status
redis-cli -u $TASKSGODZILLA_REDIS_URL ping

# Start Redis if not running
redis-server --port 6379 &

# Verify URL format
echo $TASKSGODZILLA_REDIS_URL  # Should be redis://localhost:6379/15
```

**3. Test Timeouts**
```
Error: Test execution timeout after 1800 seconds
```
Solution:
```bash
# Increase timeout for complex tests
python scripts/cli_workflow_harness.py --timeout 3600

# Use development mode for debugging
python scripts/cli_workflow_harness.py --mode development --verbose
```

**4. Missing Test Data**
```
Error: Test data directory not found
```
Solution:
```bash
# Create test data directory
mkdir -p tests/harness/data

# Use custom test data path
python scripts/cli_workflow_harness.py --test-data-path ./my-test-data
```

**5. Permission Errors**
```
Error: Permission denied writing to output directory
```
Solution:
```bash
# Create output directory with proper permissions
mkdir -p harness-output
chmod 755 harness-output

# Use custom output directory
python scripts/cli_workflow_harness.py --output-dir ./my-output
```

### Debug Mode

For detailed troubleshooting, use development mode:

```bash
python scripts/cli_workflow_harness.py --mode development \
  --verbose --log-file debug.log \
  --components onboarding
```

This provides:
- Detailed execution logs
- Full error traces
- Component-level timing
- Environment validation details
- Test data generation logs

### Getting Help

```bash
# Show all available options
python scripts/cli_workflow_harness.py --help

# Show version and environment info
python scripts/cli_workflow_harness.py --mode development --verbose | head -20
```

## Integration with Existing Workflows

### With TasksGodzilla CLI

The harness integrates seamlessly with existing TasksGodzilla workflows:

```bash
# Test after onboarding a new project
python scripts/onboard_repo.py --repo-url https://github.com/example/repo
python scripts/cli_workflow_harness.py --mode component --components onboarding

# Validate protocol execution
python scripts/protocol_pipeline.py create --name "test-protocol"
python scripts/cli_workflow_harness.py --mode component --components protocol
```

### With CI Scripts

The harness works with existing CI infrastructure:

```bash
# Use with existing bootstrap
scripts/ci/bootstrap.sh
python scripts/cli_workflow_harness.py --mode ci

# Integrate with existing test pipeline
scripts/ci/test.sh  # Run unit tests first
python scripts/cli_workflow_harness.py --mode regression  # Then integration tests
```

### With Quality Orchestrator

Combine with quality validation:

```bash
# Run harness then quality checks
python scripts/cli_workflow_harness.py --mode full
python scripts/quality_orchestrator.py --protocol-id latest
```

This comprehensive usage guide covers all aspects of running the CLI Workflow Harness effectively. For additional examples and advanced configurations, see the integration guide and troubleshooting sections.