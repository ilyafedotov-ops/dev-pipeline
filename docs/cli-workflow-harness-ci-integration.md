# CLI Workflow Harness - CI Integration Guide

## Overview

This guide covers integrating the CLI Workflow Harness into continuous integration (CI) systems including GitHub Actions, GitLab CI, Jenkins, and other CI platforms. The harness is designed to work seamlessly with existing TasksGodzilla CI infrastructure while providing comprehensive workflow validation.

## Quick Start

### Basic CI Integration

Add the harness to your existing CI pipeline after the standard test stage:

```bash
# After running standard tests
scripts/ci/test.sh

# Run workflow harness validation
python scripts/cli_workflow_harness.py --mode ci \
  --output-format junit --output-dir ./ci-reports \
  --exit-on-failure
```

### Prerequisites

The harness integrates with existing TasksGodzilla CI infrastructure:

1. **Environment Setup**: Uses existing `scripts/ci/bootstrap.sh`
2. **Service Dependencies**: Leverages configured Redis and database
3. **Reporting**: Integrates with `scripts/ci/report.sh`
4. **Error Handling**: Follows existing CI error patterns

## CI Modes and Strategies

### 1. Full Integration Strategy

**Use Case**: Comprehensive validation on main branches and releases  
**Frequency**: On merge to main, release branches  
**Duration**: ~20-30 minutes

```bash
# Complete workflow validation
python scripts/cli_workflow_harness.py --mode full \
  --parallel --max-workers 8 \
  --output-format all --output-dir ./ci-reports \
  --exit-on-failure
```

### 2. Smoke Testing Strategy

**Use Case**: Fast feedback on pull requests  
**Frequency**: On every PR, commit  
**Duration**: ~5-8 minutes

```bash
# Quick validation of critical paths
python scripts/cli_workflow_harness.py --mode smoke \
  --output-format junit --output-dir ./ci-reports \
  --exit-on-failure
```

### 3. Regression Testing Strategy

**Use Case**: Focused testing after bug fixes  
**Frequency**: On hotfix branches, after incident resolution  
**Duration**: ~10-15 minutes

```bash
# Focus on previously failing scenarios
python scripts/cli_workflow_harness.py --mode regression \
  --output-format json --output-dir ./ci-reports \
  --exit-on-failure
```

### 4. Component Testing Strategy

**Use Case**: Testing specific areas during feature development  
**Frequency**: On feature branches  
**Duration**: Variable (5-15 minutes)

```bash
# Test specific components based on changed files
python scripts/cli_workflow_harness.py --mode component \
  --components onboarding discovery protocol \
  --output-format junit --output-dir ./ci-reports \
  --exit-on-failure
```

## Platform-Specific Integration

### GitHub Actions

#### Basic Workflow

Create `.github/workflows/harness.yml`:

```yaml
name: CLI Workflow Harness

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  harness-smoke:
    runs-on: ubuntu-latest
    if: github.event_name == 'pull_request'
    
    services:
      redis:
        image: redis:alpine
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.12'
    
    - name: Bootstrap environment
      run: scripts/ci/bootstrap.sh
      env:
        TASKSGODZILLA_DB_PATH: /tmp/tasksgodzilla-ci.sqlite
        TASKSGODZILLA_REDIS_URL: redis://localhost:6379/15
    
    - name: Run smoke tests
      run: |
        python scripts/cli_workflow_harness.py --mode smoke \
          --output-format junit --output-dir ./ci-reports \
          --exit-on-failure
      env:
        TASKSGODZILLA_DB_PATH: /tmp/tasksgodzilla-ci.sqlite
        TASKSGODZILLA_REDIS_URL: redis://localhost:6379/15
        TASKSGODZILLA_CI_PROVIDER: github
        TASKSGODZILLA_API_BASE: ${{ secrets.TASKSGODZILLA_API_BASE }}
        TASKSGODZILLA_API_TOKEN: ${{ secrets.TASKSGODZILLA_API_TOKEN }}
    
    - name: Upload test results
      uses: actions/upload-artifact@v3
      if: always()
      with:
        name: harness-smoke-results
        path: ci-reports/

    - name: Publish test results
      uses: dorny/test-reporter@v1
      if: always()
      with:
        name: Harness Smoke Tests
        path: ci-reports/*.xml
        reporter: java-junit

  harness-full:
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    
    services:
      redis:
        image: redis:alpine
        ports:
          - 6379:6379
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: tasksgodzilla_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.12'
    
    - name: Bootstrap environment
      run: scripts/ci/bootstrap.sh
      env:
        TASKSGODZILLA_DB_URL: postgresql://postgres:postgres@localhost:5432/tasksgodzilla_test
        TASKSGODZILLA_REDIS_URL: redis://localhost:6379/15
    
    - name: Run database migrations
      run: .venv/bin/alembic upgrade head
      env:
        TASKSGODZILLA_DB_URL: postgresql://postgres:postgres@localhost:5432/tasksgodzilla_test
    
    - name: Run full harness
      run: |
        python scripts/cli_workflow_harness.py --mode full \
          --parallel --max-workers 4 \
          --output-format all --output-dir ./ci-reports \
          --exit-on-failure
      env:
        TASKSGODZILLA_DB_URL: postgresql://postgres:postgres@localhost:5432/tasksgodzilla_test
        TASKSGODZILLA_REDIS_URL: redis://localhost:6379/15
        TASKSGODZILLA_CI_PROVIDER: github
        TASKSGODZILLA_API_BASE: ${{ secrets.TASKSGODZILLA_API_BASE }}
        TASKSGODZILLA_API_TOKEN: ${{ secrets.TASKSGODZILLA_API_TOKEN }}
    
    - name: Upload comprehensive results
      uses: actions/upload-artifact@v3
      if: always()
      with:
        name: harness-full-results
        path: ci-reports/
    
    - name: Publish test results
      uses: dorny/test-reporter@v1
      if: always()
      with:
        name: Harness Full Tests
        path: ci-reports/*.xml
        reporter: java-junit
```

#### Advanced GitHub Actions Configuration

For more sophisticated workflows with matrix testing:

```yaml
name: CLI Workflow Harness Matrix

on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM
  workflow_dispatch:
    inputs:
      mode:
        description: 'Harness execution mode'
        required: true
        default: 'full'
        type: choice
        options:
        - full
        - smoke
        - regression
        - component

jobs:
  harness-matrix:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, ubuntu-20.04]
        python-version: ['3.11', '3.12']
        mode: [smoke, component]
        include:
          - os: ubuntu-latest
            python-version: '3.12'
            mode: full
      fail-fast: false
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Start services
      run: |
        docker run -d -p 6379:6379 redis:alpine
        sleep 5
    
    - name: Bootstrap environment
      run: scripts/ci/bootstrap.sh
    
    - name: Run harness
      run: |
        python scripts/cli_workflow_harness.py \
          --mode ${{ github.event.inputs.mode || matrix.mode }} \
          --output-format junit \
          --output-dir ./ci-reports-${{ matrix.os }}-py${{ matrix.python-version }} \
          --exit-on-failure
      env:
        TASKSGODZILLA_DB_PATH: /tmp/tasksgodzilla-${{ matrix.os }}-py${{ matrix.python-version }}.sqlite
        TASKSGODZILLA_REDIS_URL: redis://localhost:6379/15
    
    - name: Upload results
      uses: actions/upload-artifact@v3
      if: always()
      with:
        name: harness-results-${{ matrix.os }}-py${{ matrix.python-version }}
        path: ci-reports-*/
```

### GitLab CI

#### Basic Integration

Update `.gitlab-ci.yml` to include harness stages:

```yaml
stages:
  - bootstrap
  - lint
  - typecheck
  - test
  - harness-smoke
  - harness-full
  - build

# ... existing stages ...

harness-smoke:
  stage: harness-smoke
  needs: ["test"]
  services:
    - redis:alpine
  variables:
    TASKSGODZILLA_DB_PATH: /tmp/tasksgodzilla-ci.sqlite
    TASKSGODZILLA_REDIS_URL: redis://redis:6379/15
    TASKSGODZILLA_CI_PROVIDER: gitlab
  script:
    - python scripts/cli_workflow_harness.py --mode smoke
        --output-format junit --output-dir ./ci-reports
        --exit-on-failure
  artifacts:
    when: always
    reports:
      junit: ci-reports/*.xml
    paths:
      - ci-reports/
    expire_in: 1 week
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH

harness-full:
  stage: harness-full
  needs: ["harness-smoke"]
  services:
    - redis:alpine
    - postgres:15
  variables:
    TASKSGODZILLA_DB_URL: postgresql://postgres:postgres@postgres:5432/tasksgodzilla_test
    TASKSGODZILLA_REDIS_URL: redis://redis:6379/15
    TASKSGODZILLA_CI_PROVIDER: gitlab
    POSTGRES_DB: tasksgodzilla_test
    POSTGRES_USER: postgres
    POSTGRES_PASSWORD: postgres
  before_script:
    - .venv/bin/alembic upgrade head
  script:
    - python scripts/cli_workflow_harness.py --mode full
        --parallel --max-workers 4
        --output-format all --output-dir ./ci-reports
        --exit-on-failure
  artifacts:
    when: always
    reports:
      junit: ci-reports/*.xml
    paths:
      - ci-reports/
    expire_in: 1 month
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
    - if: $CI_COMMIT_TAG
```

#### Advanced GitLab CI with Dynamic Components

```yaml
harness-component:
  stage: harness-smoke
  needs: ["test"]
  services:
    - redis:alpine
  variables:
    TASKSGODZILLA_DB_PATH: /tmp/tasksgodzilla-ci.sqlite
    TASKSGODZILLA_REDIS_URL: redis://redis:6379/15
  script:
    - |
      # Determine components based on changed files
      COMPONENTS=""
      if git diff --name-only $CI_MERGE_REQUEST_DIFF_BASE_SHA $CI_COMMIT_SHA | grep -q "scripts/onboard_repo.py\|tasksgodzilla/onboarding"; then
        COMPONENTS="$COMPONENTS onboarding"
      fi
      if git diff --name-only $CI_MERGE_REQUEST_DIFF_BASE_SHA $CI_COMMIT_SHA | grep -q "scripts/protocol_pipeline.py\|tasksgodzilla/protocol"; then
        COMPONENTS="$COMPONENTS protocol"
      fi
      if git diff --name-only $CI_MERGE_REQUEST_DIFF_BASE_SHA $CI_COMMIT_SHA | grep -q "scripts/tasksgodzilla_cli.py\|tasksgodzilla/cli"; then
        COMPONENTS="$COMPONENTS cli_interface"
      fi
      
      if [ -n "$COMPONENTS" ]; then
        python scripts/cli_workflow_harness.py --mode component \
          --components $COMPONENTS \
          --output-format junit --output-dir ./ci-reports \
          --exit-on-failure
      else
        echo "No relevant changes detected, running smoke tests"
        python scripts/cli_workflow_harness.py --mode smoke \
          --output-format junit --output-dir ./ci-reports \
          --exit-on-failure
      fi
  artifacts:
    when: always
    reports:
      junit: ci-reports/*.xml
    paths:
      - ci-reports/
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
```

### Jenkins

#### Declarative Pipeline

Create `Jenkinsfile`:

```groovy
pipeline {
    agent any
    
    environment {
        TASKSGODZILLA_DB_PATH = '/tmp/tasksgodzilla-jenkins.sqlite'
        TASKSGODZILLA_REDIS_URL = 'redis://localhost:6379/15'
        TASKSGODZILLA_CI_PROVIDER = 'jenkins'
    }
    
    stages {
        stage('Bootstrap') {
            steps {
                sh 'scripts/ci/bootstrap.sh'
            }
        }
        
        stage('Standard Tests') {
            steps {
                sh 'scripts/ci/test.sh'
            }
        }
        
        stage('Harness Smoke') {
            when {
                anyOf {
                    changeRequest()
                    branch 'develop'
                }
            }
            steps {
                sh '''
                    python scripts/cli_workflow_harness.py --mode smoke \
                      --output-format junit --output-dir ./ci-reports \
                      --exit-on-failure
                '''
            }
            post {
                always {
                    publishTestResults testResultsPattern: 'ci-reports/*.xml'
                    archiveArtifacts artifacts: 'ci-reports/**/*', allowEmptyArchive: true
                }
            }
        }
        
        stage('Harness Full') {
            when {
                anyOf {
                    branch 'main'
                    branch 'release/*'
                }
            }
            steps {
                sh '''
                    python scripts/cli_workflow_harness.py --mode full \
                      --parallel --max-workers 4 \
                      --output-format all --output-dir ./ci-reports \
                      --exit-on-failure
                '''
            }
            post {
                always {
                    publishTestResults testResultsPattern: 'ci-reports/*.xml'
                    archiveArtifacts artifacts: 'ci-reports/**/*', allowEmptyArchive: true
                }
            }
        }
    }
    
    post {
        always {
            cleanWs()
        }
        failure {
            emailext (
                subject: "Harness Failed: ${env.JOB_NAME} - ${env.BUILD_NUMBER}",
                body: "The CLI Workflow Harness failed. Check the build logs for details.",
                to: "${env.CHANGE_AUTHOR_EMAIL}"
            )
        }
    }
}
```

#### Scripted Pipeline with Matrix

```groovy
node {
    def modes = ['smoke', 'component', 'regression']
    def parallelStages = [:]
    
    stage('Checkout') {
        checkout scm
    }
    
    stage('Bootstrap') {
        sh 'scripts/ci/bootstrap.sh'
    }
    
    modes.each { mode ->
        parallelStages["Harness ${mode}"] = {
            stage("Harness ${mode}") {
                sh """
                    python scripts/cli_workflow_harness.py --mode ${mode} \
                      --output-format junit \
                      --output-dir ./ci-reports-${mode} \
                      --exit-on-failure
                """
                publishTestResults testResultsPattern: "ci-reports-${mode}/*.xml"
            }
        }
    }
    
    parallel parallelStages
}
```

## Configuration Management

### Environment Variables

The harness uses standard TasksGodzilla environment variables:

```bash
# Required
export TASKSGODZILLA_DB_PATH="/tmp/tasksgodzilla-ci.sqlite"
export TASKSGODZILLA_REDIS_URL="redis://localhost:6379/15"

# CI-specific
export TASKSGODZILLA_CI_PROVIDER="github"  # or "gitlab", "jenkins"
export TASKSGODZILLA_API_BASE="https://api.tasksgodzilla.com"
export TASKSGODZILLA_API_TOKEN="your-api-token"

# Optional webhook integration
export TASKSGODZILLA_WEBHOOK_TOKEN="webhook-secret"
export TASKSGODZILLA_PROTOCOL_RUN_ID="protocol-123"

# Performance tuning
export TASKSGODZILLA_INLINE_RQ_WORKER="true"  # For testing
```

### CI Configuration Files

Create reusable configuration files for different CI scenarios:

**ci-smoke.json**:
```json
{
  "mode": "smoke",
  "parallel": true,
  "max_workers": 2,
  "timeout": 600,
  "components": ["onboarding", "cli_interface"],
  "output_formats": ["junit", "json"]
}
```

**ci-full.json**:
```json
{
  "mode": "full",
  "parallel": true,
  "max_workers": 8,
  "timeout": 2400,
  "components": [],
  "output_formats": ["junit", "json", "text"]
}
```

**ci-regression.json**:
```json
{
  "mode": "regression",
  "parallel": true,
  "max_workers": 4,
  "timeout": 1200,
  "components": ["error_conditions", "failure_detection"],
  "output_formats": ["junit", "json"]
}
```

Use in CI:
```bash
python scripts/cli_workflow_harness.py --config ci-smoke.json --exit-on-failure
```

## Service Dependencies

### Redis Setup

The harness requires Redis for queue operations:

**Docker Compose** (for local CI):
```yaml
version: '3.8'
services:
  redis:
    image: redis:alpine
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data

volumes:
  redis_data:
```

**Kubernetes** (for cluster CI):
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:alpine
        ports:
        - containerPort: 6379
---
apiVersion: v1
kind: Service
metadata:
  name: redis
spec:
  selector:
    app: redis
  ports:
  - port: 6379
    targetPort: 6379
```

### Database Setup

**SQLite** (recommended for CI):
```bash
# Automatic setup, no additional configuration needed
export TASKSGODZILLA_DB_PATH="/tmp/tasksgodzilla-ci.sqlite"
```

**PostgreSQL** (for comprehensive testing):
```bash
# Using Docker
docker run -d --name postgres-ci \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=tasksgodzilla_test \
  -p 5432:5432 postgres:15

export TASKSGODZILLA_DB_URL="postgresql://postgres:postgres@localhost:5432/tasksgodzilla_test"

# Run migrations
.venv/bin/alembic upgrade head
```

## Output Formats and Reporting

### JUnit XML Integration

The harness generates JUnit XML compatible with most CI systems:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<testsuites name="CLI Workflow Harness" tests="156" failures="14" time="1247.32">
  <testsuite name="onboarding" tests="23" failures="1" time="156.7">
    <testcase name="test_onboard_python_project" classname="onboarding" time="12.3"/>
    <testcase name="test_onboard_invalid_repo" classname="onboarding" time="5.1">
      <failure message="Repository validation failed" type="ValidationError">
        Repository URL validation failed: invalid format
        Expected: https://github.com/user/repo
        Actual: invalid-url
      </failure>
    </testcase>
  </testsuite>
</testsuites>
```

### JSON Reports for Automation

Machine-readable JSON reports for further processing:

```json
{
  "execution_id": "ci_20231211_143022",
  "mode": "smoke",
  "ci_provider": "github",
  "branch": "feature/new-workflow",
  "commit_sha": "abc123def456",
  "total_tests": 45,
  "passed_tests": 42,
  "failed_tests": 3,
  "success_rate": 93.3,
  "duration": 387.5,
  "critical_failures": [
    {
      "component": "onboarding",
      "test": "test_onboard_invalid_repo",
      "error": "Repository validation failed"
    }
  ],
  "recommendations": [
    {
      "priority": 1,
      "category": "fix",
      "description": "Improve repository URL validation"
    }
  ]
}
```

### Integration with Existing Reporting

The harness integrates with TasksGodzilla's existing reporting via `scripts/ci/report.sh`:

```bash
# Automatic integration
python scripts/cli_workflow_harness.py --mode ci

# Manual reporting
scripts/ci/report.sh success  # or failure
```

## Performance Optimization

### Parallel Execution

Optimize CI performance with parallel execution:

```bash
# Adjust workers based on CI environment
python scripts/cli_workflow_harness.py --mode full \
  --parallel --max-workers 8  # For powerful CI runners

python scripts/cli_workflow_harness.py --mode smoke \
  --parallel --max-workers 2  # For resource-constrained environments
```

### Caching Strategies

**GitHub Actions**:
```yaml
- name: Cache Python dependencies
  uses: actions/cache@v3
  with:
    path: .venv
    key: ${{ runner.os }}-python-${{ hashFiles('requirements-orchestrator.txt') }}

- name: Cache test data
  uses: actions/cache@v3
  with:
    path: tests/harness/data
    key: ${{ runner.os }}-test-data-${{ hashFiles('tests/harness/data/**') }}
```

**GitLab CI**:
```yaml
cache:
  key: ${CI_COMMIT_REF_SLUG}
  paths:
    - .venv/
    - tests/harness/data/
```

### Resource Management

Monitor and optimize resource usage:

```bash
# Set memory limits
python scripts/cli_workflow_harness.py --mode full \
  --parallel --max-workers 4  # Adjust based on available memory

# Set timeouts appropriately
python scripts/cli_workflow_harness.py --mode smoke \
  --timeout 600  # 10 minutes for smoke tests

python scripts/cli_workflow_harness.py --mode full \
  --timeout 2400  # 40 minutes for full tests
```

## Troubleshooting CI Issues

### Common CI Problems

**1. Redis Connection Issues**
```bash
# Check Redis availability
redis-cli -u $TASKSGODZILLA_REDIS_URL ping

# Common solutions
export TASKSGODZILLA_REDIS_URL="redis://redis:6379/15"  # Docker service name
export TASKSGODZILLA_REDIS_URL="redis://localhost:6379/15"  # Local Redis
```

**2. Database Migration Issues**
```bash
# Ensure migrations run before harness
.venv/bin/alembic upgrade head

# Check database connectivity
python -c "
import os
from tasksgodzilla.storage import get_db_connection
conn = get_db_connection()
print('Database connection successful')
"
```

**3. Permission Issues**
```bash
# Ensure output directory is writable
mkdir -p ci-reports
chmod 755 ci-reports

# Check Python path
export PYTHONPATH="${PYTHONPATH:-.}"
```

**4. Timeout Issues**
```bash
# Increase timeouts for slow CI environments
python scripts/cli_workflow_harness.py --timeout 3600

# Use smoke mode for faster feedback
python scripts/cli_workflow_harness.py --mode smoke
```

**5. Memory Issues**
```bash
# Reduce parallel workers
python scripts/cli_workflow_harness.py --max-workers 2

# Use component mode to test incrementally
python scripts/cli_workflow_harness.py --mode component --components onboarding
```

### Debug Mode in CI

Enable debug mode for troubleshooting:

```bash
python scripts/cli_workflow_harness.py --mode development \
  --verbose --log-file ci-debug.log \
  --components onboarding
```

### CI-Specific Environment Validation

Validate CI environment before running tests:

```bash
# Check required services
redis-cli ping || echo "Redis not available"
python -c "import psycopg2" || echo "PostgreSQL client not available"

# Check environment variables
env | grep TASKSGODZILLA || echo "TasksGodzilla environment not configured"

# Check file permissions
touch ci-reports/test.txt && rm ci-reports/test.txt || echo "Output directory not writable"
```

## Best Practices

### 1. Staged Rollout

Implement harness integration gradually:

1. **Week 1**: Add smoke tests to PR validation
2. **Week 2**: Add component tests for changed areas
3. **Week 3**: Add full tests to main branch
4. **Week 4**: Add regression tests to release process

### 2. Failure Handling

Handle failures gracefully:

```bash
# Continue on non-critical failures
python scripts/cli_workflow_harness.py --mode smoke || echo "Harness failed but continuing"

# Fail fast on critical issues
python scripts/cli_workflow_harness.py --mode smoke --exit-on-failure
```

### 3. Resource Monitoring

Monitor CI resource usage:

```yaml
# GitHub Actions
- name: Monitor resources
  run: |
    echo "CPU cores: $(nproc)"
    echo "Memory: $(free -h)"
    echo "Disk: $(df -h)"
```

### 4. Artifact Management

Manage test artifacts effectively:

```yaml
# Keep artifacts for failed builds longer
artifacts:
  when: on_failure
  expire_in: 1 month
  paths:
    - ci-reports/
    - harness-debug.log
```

### 5. Notification Strategy

Set up appropriate notifications:

```yaml
# GitHub Actions
- name: Notify on failure
  if: failure()
  uses: 8398a7/action-slack@v3
  with:
    status: failure
    text: "CLI Workflow Harness failed on ${{ github.ref }}"
```

This comprehensive CI integration guide provides everything needed to successfully integrate the CLI Workflow Harness into various CI systems while following best practices for performance, reliability, and maintainability.