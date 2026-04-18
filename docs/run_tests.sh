#!/usr/bin/env bash
# DevGodzilla Functional Test Suite — Sections A through E + G,H,I
# Backend: localhost:8000, API prefix /api/v1
set -o pipefail
PLAN_PATH=""

BASE="http://localhost:8000/api/v1"
PID=24  # Pre-onboarded test project

PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0
RESULTS=""

record() {
  local status="$1"
  local label="$2"
  local code="${3:-}"
  local body="${4:-}"
  
  body_short=$(echo "$body" | head -c 300)
  
  if [ "$status" = "PASS" ]; then
    PASS_COUNT=$((PASS_COUNT + 1))
    RESULTS="$RESULTS\n✅ PASS [$code] $label"
  elif [ "$status" = "FAIL" ]; then
    FAIL_COUNT=$((FAIL_COUNT + 1))
    RESULTS="$RESULTS\n❌ FAIL [$code] $label"
  else
    SKIP_COUNT=$((SKIP_COUNT + 1))
    RESULTS="$RESULTS\n⏭️  SKIP $label"
  fi
  RESULTS="$RESULTS\n   BODY: $body_short\n"
}

# Helper: curl + extract code + body
do_curl() {
  local method="$1"
  local url="$2"
  local body="$3"
  local maxtime="${4:-60}"
  
  if [ "$method" = "GET" ]; then
    resp=$(curl -s -w "\n___HTTP___%{http_code}" --max-time "$maxtime" "$BASE$url" 2>&1) || true
  else
    if [ -z "$body" ] || [ "$body" = "{}" ]; then
      resp=$(curl -s -w "\n___HTTP___%{http_code}" --max-time "$maxtime" -X "$method" "$BASE$url" \
        -H "Content-Type: application/json" -d '{}' 2>&1) || true
    else
      resp=$(curl -s -w "\n___HTTP___%{http_code}" --max-time "$maxtime" -X "$method" "$BASE$url" \
        -H "Content-Type: application/json" -d "$body" 2>&1) || true
    fi
  fi
  
  http_code=$(echo "$resp" | grep "___HTTP___" | sed 's/___HTTP___//')
  body_content=$(echo "$resp" | grep -v "___HTTP___" | head -c 300)
}

test_endpoint() {
  local label="$1"
  local method="$2"
  local url="$3"
  local body="$4"
  local expected="$5"
  local maxtime="${6:-60}"
  
  do_curl "$method" "$url" "$body" "$maxtime"
  
  if [ "$http_code" = "$expected" ]; then
    record "PASS" "$label" "$http_code" "$body_content"
  else
    record "FAIL" "$label" "got:$http_code exp:$expected" "$body_content"
  fi
}

echo "=============================================="
echo "DevGodzilla Functional Test Suite"
echo "=============================================="
echo "Base URL: $BASE"
echo "Test Project ID: $PID"
echo "Time: $(date -Iseconds)"
echo "=============================================="
echo ""

# ============================================================
# SECTION A: Project Onboarding Flow
# ============================================================
echo "Running Section A: Project Onboarding Flow..."

# A.1 Create project
do_curl POST "/projects" '{"name":"test-onboard-func","git_url":"https://github.com/ilyafedotov-ops/dev-pipeline","base_branch":"main","auto_onboard":false}'
A1_PID=$(echo "$body_content" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null || echo "0")
if [ "$http_code" = "200" ] && [ "$A1_PID" != "0" ]; then
  record "PASS" "A.1: Create project → DB record (ID=$A1_PID)" "$http_code" "$body_content"
else
  record "FAIL" "A.1: Create project" "got:$http_code" "$body_content"
fi

# A.1b Verify in listing
test_endpoint "A.1b: GET /projects includes project" "GET" "/projects" "" "200"

# A.2 Start onboarding (no discovery)
do_curl POST "/projects/$A1_PID/actions/onboard" '{"clone_if_missing":true,"run_discovery_agent":false}' "90"
if [ "$http_code" = "200" ] || [ "$http_code" = "202" ]; then
  record "PASS" "A.2: Start onboarding → $http_code" "$http_code" "$body_content"
else
  record "FAIL" "A.2: Start onboarding" "got:$http_code exp:200/202" "$body_content"
fi

# A.2b Poll status
do_curl GET "/projects/$A1_PID/onboarding" ""
if [ "$http_code" = "200" ]; then
  OB_STATUS=$(echo "$body_content" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])" 2>/dev/null || echo "unknown")
  record "PASS" "A.2b: Onboarding status=$OB_STATUS" "$http_code" "$body_content"
else
  record "FAIL" "A.2b: Poll onboarding status" "got:$http_code" "$body_content"
fi

# A.3 Verify files on disk (project 24 is known onboarded)
LOCAL="/home/ilya/dev-pipeline/projects/24/dev-pipeline"
if [ -f "$LOCAL/.specify/memory/constitution.md" ]; then
  record "PASS" "A.3: constitution.md exists" "disk" "$LOCAL/.specify/memory/constitution.md"
else
  record "FAIL" "A.3: constitution.md missing" "disk" "$LOCAL/.specify/memory/constitution.md"
fi
if [ -d "$LOCAL/.specify/templates" ]; then
  record "PASS" "A.3: .specify/templates/ exists" "disk" ""
else
  record "FAIL" "A.3: .specify/templates/ missing" "disk" ""
fi
if [ -d "$LOCAL/specs" ]; then
  record "PASS" "A.3: specs/ exists" "disk" ""
else
  record "FAIL" "A.3: specs/ missing" "disk" ""
fi

# A.4 Verify events
test_endpoint "A.4: GET /events/recent for project" "GET" "/events/recent?project_id=$PID&limit=5" "" "200"

# A.6a Non-existent project onboard
test_endpoint "A.6a: Onboard non-existent project → 404" "POST" "/projects/99999/actions/onboard" "{}" "404"

# A.6b Project with no git_url
do_curl POST "/projects" '{"name":"test-no-git"}'
NOGIT_PID=$(echo "$body_content" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null || echo "0")
# Onboard project without git_url — may return 400 or 404 or 500 depending on behavior
do_curl POST "/projects/$NOGIT_PID/actions/onboard" '{}'
if [ "$http_code" != "200" ]; then
  record "PASS" "A.6b: Onboard project w/o git_url → error ($http_code)" "$http_code" "$body_content"
else
  record "FAIL" "A.6b: Onboard project w/o git_url should error" "got:$http_code" "$body_content"
fi

# Cleanup
curl -s -X DELETE "$BASE/projects/$A1_PID" > /dev/null 2>&1
curl -s -X DELETE "$BASE/projects/$NOGIT_PID" > /dev/null 2>&1

echo ""

# ============================================================
# SECTION B: Worktree Management
# ============================================================
echo "Running Section B: Worktree Management..."

test_endpoint "B.1: GET /projects/$PID/branches" "GET" "/projects/$PID/branches" "" "200"

test_endpoint "B.2: Create branch test-wt-branch" "POST" "/projects/$PID/branches" \
  '{"name":"test-wt-branch","base_ref":"main","checkout":false}' "200"

# Verify branch
do_curl GET "/projects/$PID/branches" ""
B_NAMES=$(echo "$body_content" | python3 -c "
import sys,json
try:
  branches = json.load(sys.stdin)
  print(','.join([b['name'] for b in branches]))
except: print('')
" 2>/dev/null)
if echo "$B_NAMES" | grep -q "test-wt-branch"; then
  record "PASS" "B.2b: Branch test-wt-branch in listing" "200" "$B_NAMES"
else
  record "FAIL" "B.2b: Branch not found in listing" "200" "$B_NAMES"
fi

test_endpoint "B.4: Delete branch test-wt-branch" "POST" "/projects/$PID/branches/test-wt-branch/delete" "" "200"

test_endpoint "B.5: GET /projects/$PID/worktrees" "GET" "/projects/$PID/worktrees" "" "200"

echo ""

# ============================================================
# SECTION C: SpecKit Full Flow
# ============================================================
echo "Running Section C: SpecKit Full Flow..."

# C.1 Specify — uses 'description' field (min_length=10)
do_curl POST "/speckit/specify" "{\"project_id\":$PID,\"description\":\"Add user authentication with OAuth2 and JWT tokens for secure API access\",\"feature_name\":\"user-auth\"}" "30"
if [ "$http_code" = "200" ]; then
  SPEC_RUN_ID=$(echo "$body_content" | python3 -c "
import sys,json
d=json.load(sys.stdin)
print(d.get('spec_run_id','none'))
" 2>/dev/null || echo "none")
  SPEC_PATH=$(echo "$body_content" | python3 -c "
import sys,json
d=json.load(sys.stdin)
print(d.get('spec_path',''))
" 2>/dev/null || echo "")
  record "PASS" "C.1: SpecKit specify → spec_run_id=$SPEC_RUN_ID" "$http_code" "$body_content"
else
  record "FAIL" "C.1: SpecKit specify" "got:$http_code" "$body_content"
  SPEC_RUN_ID="none"
  SPEC_PATH=""
fi

# C.2 Status
test_endpoint "C.2: GET /speckit/status/$PID" "GET" "/speckit/status/$PID" "" "200"

# C.3 Plan — requires spec_path
if [ -n "$SPEC_PATH" ] && [ "$SPEC_RUN_ID" != "none" ]; then
  do_curl POST "/speckit/plan" "{\"project_id\":$PID,\"spec_path\":\"$SPEC_PATH\",\"spec_run_id\":$SPEC_RUN_ID}" "60"
  PLAN_PATH=$(echo "$body_content" | python3 -c "
import sys,json
d=json.load(sys.stdin)
print(d.get('plan_path',''))
" 2>/dev/null || echo "")
  if [ "$http_code" = "200" ]; then
    record "PASS" "C.3: SpecKit plan" "$http_code" "$body_content"
  else
    record "FAIL" "C.3: SpecKit plan" "got:$http_code" "$body_content"
  fi
else
  record "SKIP" "C.3: SpecKit plan (no spec_run_id)" "" ""
fi

# C.4 Tasks — requires plan_path
if [ -n "$PLAN_PATH" ] && [ "$SPEC_RUN_ID" != "none" ]; then
  do_curl POST "/speckit/tasks" "{\"project_id\":$PID,\"plan_path\":\"$PLAN_PATH\",\"spec_run_id\":$SPEC_RUN_ID}" "60"
  if [ "$http_code" = "200" ]; then
    record "PASS" "C.4: SpecKit tasks" "$http_code" "$body_content"
  else
    record "FAIL" "C.4: SpecKit tasks" "got:$http_code" "$body_content"
  fi
else
  record "SKIP" "C.4: SpecKit tasks (no plan_path)" "" ""
fi

# C.5 Analyze
if [ -n "$SPEC_PATH" ] && [ "$SPEC_RUN_ID" != "none" ]; then
  do_curl POST "/speckit/analyze" "{\"project_id\":$PID,\"spec_path\":\"$SPEC_PATH\",\"spec_run_id\":$SPEC_RUN_ID}" "60"
  if [ "$http_code" = "200" ]; then
    record "PASS" "C.5: SpecKit analyze" "$http_code" "$body_content"
  else
    record "FAIL" "C.5: SpecKit analyze" "got:$http_code" "$body_content"
  fi
else
  record "SKIP" "C.5: SpecKit analyze" "" ""
fi

# C.6 Checklist
if [ -n "$SPEC_PATH" ] && [ "$SPEC_RUN_ID" != "none" ]; then
  do_curl POST "/speckit/checklist" "{\"project_id\":$PID,\"spec_path\":\"$SPEC_PATH\",\"spec_run_id\":$SPEC_RUN_ID}" "60"
  if [ "$http_code" = "200" ]; then
    record "PASS" "C.6: SpecKit checklist" "$http_code" "$body_content"
  else
    record "FAIL" "C.6: SpecKit checklist" "got:$http_code" "$body_content"
  fi
else
  record "SKIP" "C.6: SpecKit checklist" "" ""
fi

# C.7 Workflow (full pipeline with a new feature)
do_curl POST "/speckit/workflow" "{\"project_id\":$PID,\"description\":\"Build a dashboard with charts and real-time data visualization widgets\",\"feature_name\":\"dashboard\"}" "90"
if [ "$http_code" = "200" ]; then
  WF_SPEC_RUN=$(echo "$body_content" | python3 -c "
import sys,json
d=json.load(sys.stdin)
print(d.get('spec_run_id','none'))
" 2>/dev/null || echo "none")
  record "PASS" "C.7: SpecKit workflow → spec_run_id=$WF_SPEC_RUN" "$http_code" "$body_content"
else
  record "FAIL" "C.7: SpecKit workflow" "got:$http_code" "$body_content"
  WF_SPEC_RUN="none"
fi

# C.8 Cleanup (via spec-runs endpoint)
if [ "$SPEC_RUN_ID" != "none" ]; then
  test_endpoint "C.8: Cleanup spec run $SPEC_RUN_ID" "POST" "/speckit/spec-runs/$SPEC_RUN_ID/cleanup" '{}' "200"
else
  record "SKIP" "C.8: Cleanup (no spec_run_id)" "" ""
fi

# C.9 Implement — create new spec for it
do_curl POST "/speckit/specify" "{\"project_id\":$PID,\"description\":\"Implement a simple hello world REST endpoint that returns JSON\",\"feature_name\":\"impl-test\"}" "30"
IMPL_SR=$(echo "$body_content" | python3 -c "
import sys,json
d=json.load(sys.stdin)
print(d.get('spec_run_id','none'))
" 2>/dev/null || echo "none")
IMPL_SP=$(echo "$body_content" | python3 -c "
import sys,json
d=json.load(sys.stdin)
print(d.get('spec_path',''))
" 2>/dev/null || echo "")

if [ "$IMPL_SR" != "none" ] && [ -n "$IMPL_SP" ]; then
  do_curl POST "/speckit/implement" "{\"project_id\":$PID,\"spec_path\":\"$IMPL_SP\",\"spec_run_id\":$IMPL_SR}" "60"
  if [ "$http_code" = "200" ]; then
    record "PASS" "C.9: SpecKit implement" "$http_code" "$body_content"
  else
    record "FAIL" "C.9: SpecKit implement" "got:$http_code" "$body_content"
  fi
else
  record "SKIP" "C.9: SpecKit implement (specify failed)" "" ""
fi

# C.10 Specifications listing
test_endpoint "C.10a: GET /specifications" "GET" "/specifications" "" "200"
test_endpoint "C.10b: GET /specifications?limit=5" "GET" "/specifications?limit=5" "" "200"

echo ""

# ============================================================
# SECTION D: AI Agent Execution
# ============================================================
echo "Running Section D: AI Agent Execution..."

test_endpoint "D.1: GET /agents/health" "GET" "/agents/health" "" "200"

# D.2 Per-agent tests
for agent in opencode claude-code codex gemini-cli; do
  test_endpoint "D.2: POST /agents/$agent/test" "POST" "/agents/$agent/test" '{}' "200"
done

# D.3 Individual health
for agent in opencode claude-code codex gemini-cli; do
  test_endpoint "D.3: GET /agents/$agent/health" "GET" "/agents/$agent/health" "" "200"
done

test_endpoint "D.5: GET /agents (list)" "GET" "/agents" "" "200"
test_endpoint "D.6: GET /agents/metrics" "GET" "/agents/metrics" "" "200"

# D.7 Agent update (try PUT)
do_curl PUT "/agents/opencode" '{"name":"opencode","engine_id":"opencode"}'
if [ "$http_code" = "200" ]; then
  record "PASS" "D.7: PUT /agents/opencode" "$http_code" "$body_content"
else
  record "FAIL" "D.7: PUT /agents/opencode (method may not be supported)" "got:$http_code" "$body_content"
fi

echo ""

# ============================================================
# SECTION E: Brownfield + Task Cycle
# ============================================================
echo "Running Section E: Brownfield + Task Cycle..."

# E.1 Brownfield run — requires feature_request
do_curl POST "/projects/$PID/brownfield/run" '{"feature_request":"Analyze existing codebase and identify improvement areas","output_mode":"protocol"}' "90"
if [ "$http_code" = "200" ] || [ "$http_code" = "202" ]; then
  record "PASS" "E.1: Brownfield run" "$http_code" "$body_content"
else
  record "FAIL" "E.1: Brownfield run" "got:$http_code" "$body_content"
fi

test_endpoint "E.2: GET /projects/$PID/task-cycle" "GET" "/projects/$PID/task-cycle" "" "200"

# E.3 Work item lifecycle
do_curl GET "/projects/$PID/task-cycle" ""
WI_ID=$(echo "$body_content" | python3 -c "
import sys,json
items = json.load(sys.stdin)
print(items[0]['id'] if items else 'none')
" 2>/dev/null || echo "none")

if [ "$WI_ID" != "none" ]; then
  test_endpoint "E.3a: Build context WI $WI_ID" "POST" "/work-items/$WI_ID/build-context" '{"refresh":false}' "200"
  test_endpoint "E.3b: Implement WI $WI_ID" "POST" "/work-items/$WI_ID/actions/implement" '{"owner_agent":"opencode"}' "200"
  test_endpoint "E.3c: Review WI $WI_ID" "POST" "/work-items/$WI_ID/actions/review" '{}' "200"
  test_endpoint "E.3d: QA WI $WI_ID" "POST" "/work-items/$WI_ID/actions/qa" '{}' "200"
  test_endpoint "E.3e: Mark PR ready WI $WI_ID" "POST" "/work-items/$WI_ID/actions/mark-pr-ready" '{}' "200"
else
  record "SKIP" "E.3: Work item lifecycle (no items)" "" ""
fi

test_endpoint "E.4: GET /projects/$PID/protocols" "GET" "/projects/$PID/protocols" "" "200"

echo ""

# ============================================================
# SECTION G: Sprint + Execution Layer
# ============================================================
echo "Running Section G: Sprint + Execution Layer..."

test_endpoint "G.1: GET /sprints" "GET" "/sprints" "" "200"

# Create sprint
do_curl POST "/sprints" "{\"project_id\":$PID,\"name\":\"Test Sprint\",\"goal\":\"Testing\",\"status\":\"planning\",\"start_date\":\"2026-04-19\",\"end_date\":\"2026-05-03\"}"
G2_SID=$(echo "$body_content" | python3 -c "
import sys,json
d=json.load(sys.stdin)
print(d.get('id','none'))
" 2>/dev/null || echo "none")
if [ "$http_code" = "200" ] && [ "$G2_SID" != "none" ]; then
  record "PASS" "G.2: Create sprint (ID=$G2_SID)" "$http_code" "$body_content"
else
  record "FAIL" "G.2: Create sprint" "got:$http_code" "$body_content"
fi

if [ "$G2_SID" != "none" ]; then
  test_endpoint "G.3a: GET /sprints/$G2_SID/tasks" "GET" "/sprints/$G2_SID/tasks" "" "200"
  test_endpoint "G.4: GET /sprints/$G2_SID/metrics" "GET" "/sprints/$G2_SID/metrics" "" "200"
  curl -s -X DELETE "$BASE/sprints/$G2_SID" > /dev/null 2>&1
else
  record "SKIP" "G.3/G.4: Sprint tasks/metrics (no sprint)" "" ""
fi

echo ""

# ============================================================
# SECTION H: Event System
# ============================================================
echo "Running Section H: Event System..."

# H.1 SSE stream — just check it starts with 200 and correct content type
H1_CT=$(curl -s -o /dev/null -w "%{http_code}|%{content_type}" --max-time 2 "$BASE/events?limit=1" 2>/dev/null || true)
H1_CODE=$(echo "$H1_CT" | cut -d'|' -f1)
H1_TYPE=$(echo "$H1_CT" | cut -d'|' -f2)
if [ "$H1_CODE" = "200" ]; then
  record "PASS" "H.1: GET /events SSE stream (ct=$H1_TYPE)" "$H1_CODE" ""
else
  record "FAIL" "H.1: GET /events SSE stream" "got:$H1_CODE" ""
fi

test_endpoint "H.2: GET /events/recent" "GET" "/events/recent?limit=5" "" "200"

echo ""

# ============================================================
# SECTION I: Policy Packs + Constitution
# ============================================================
echo "Running Section I: Policy Packs + Constitution..."

test_endpoint "I.1: GET /policy_packs" "GET" "/policy_packs" "" "200"

# I.2 Create policy pack
do_curl POST "/policy_packs" '{"key":"test-func-policy","version":"1.0.0","name":"Test Policy","description":"Functional test policy","status":"active","pack":{"rules":[]}}'
if [ "$http_code" = "200" ]; then
  record "PASS" "I.2: Create policy pack" "$http_code" "$body_content"
else
  record "FAIL" "I.2: Create policy pack" "got:$http_code" "$body_content"
fi

test_endpoint "I.3: GET /policy_packs/test-func-policy" "GET" "/policy_packs/test-func-policy" "" "200"

# I.5 Clarifications
do_curl GET "/projects/$PID/clarifications" ""
if [ "$http_code" = "200" ]; then
  record "PASS" "I.5: GET /projects/$PID/clarifications" "$http_code" "$body_content"
else
  record "FAIL" "I.5: Clarifications" "got:$http_code" "$body_content"
fi

echo ""
echo "=============================================="
echo "TEST SUMMARY"
echo "=============================================="
echo -e "$RESULTS"
echo "=============================================="
echo "PASS: $PASS_COUNT"
echo "FAIL: $FAIL_COUNT"
echo "SKIP: $SKIP_COUNT"
echo "TOTAL: $((PASS_COUNT + FAIL_COUNT + SKIP_COUNT))"
echo "=============================================="
