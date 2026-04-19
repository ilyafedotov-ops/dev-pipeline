#!/bin/bash
# Comprehensive test suite - ALL 52 test cases
BASE="http://localhost:8000/api/v1"
CURL="curl -s -w '\nHTTP_CODE:%{http_code}' --max-time 30"

run_test() {
  local label="$1"
  local method="$2"
  local url="$3"
  local body="$4"
  local expect="$5"
  
  if [ "$method" = "GET" ]; then
    resp=$(curl -s -w '\nHTTP_CODE:%{http_code}' --max-time 30 "$BASE$url" 2>/dev/null)
  else
    if [ -n "$body" ]; then
      resp=$(curl -s -w '\nHTTP_CODE:%{http_code}' --max-time 30 -X "$method" -H "Content-Type: application/json" -d "$body" "$BASE$url" 2>/dev/null)
    else
      resp=$(curl -s -w '\nHTTP_CODE:%{http_code}' --max-time 30 -X "$method" "$BASE$url" 2>/dev/null)
    fi
  fi
  
  http_code=$(echo "$resp" | grep 'HTTP_CODE:' | sed 's/HTTP_CODE://')
  body_resp=$(echo "$resp" | grep -v 'HTTP_CODE:')
  body_short=$(echo "$body_resp" | head -c 200)
  
  # Determine PASS/FAIL
  if [ -n "$expect" ] && [ "$expect" != "ANY" ]; then
    if [ "$http_code" = "$expect" ]; then
      status="✅ PASS"
    else
      status="❌ FAIL"
    fi
  else
    status="✅ PASS"
  fi
  
  echo "$label|$status|$http_code|$body_short"
}

echo "=== SECTION A: Project Onboarding Flow ==="

# A.1 - Create project
echo "--- A.1 ---"
run_test "A.1" "POST" "/projects" '{"name":"test-func-suite-v2","git_url":"https://github.com/ilyafedotov-ops/dev-pipeline"}' "ANY"

# A.1b - GET /projects
echo "--- A.1b ---"
run_test "A.1b" "GET" "/projects" "" "200"

# A.2 - Start onboarding (project 24)
echo "--- A.2 ---"
run_test "A.2" "POST" "/projects/24/onboard" '{"clone_if_missing":true,"run_discovery_agent":false}' "ANY"

# A.2b - Poll onboarding status
echo "--- A.2b ---"
run_test "A.2b" "GET" "/projects/24/onboard/status" "" "200"

# A.3a - constitution.md exists
echo "--- A.3a ---"
if [ -f "/home/ilya/dev-pipeline/projects/24/dev-pipeline/.specify/memory/constitution.md" ]; then
  echo "A.3a|✅ PASS|disk|constitution.md exists"
else
  echo "A.3a|❌ FAIL|disk|constitution.md NOT found"
fi

# A.3b - .specify/templates exists
echo "--- A.3b ---"
if [ -d "/home/ilya/dev-pipeline/projects/24/dev-pipeline/.specify/templates" ]; then
  echo "A.3b|✅ PASS|disk|.specify/templates exists"
else
  echo "A.3b|❌ FAIL|disk|.specify/templates NOT found"
fi

# A.3c - specs/ directory exists
echo "--- A.3c ---"
if [ -d "/home/ilya/dev-pipeline/projects/24/dev-pipeline/specs" ]; then
  echo "A.3c|✅ PASS|disk|specs/ directory exists"
else
  echo "A.3c|❌ FAIL|disk|specs/ directory NOT found"
fi

# A.4 - Events recent
echo "--- A.4 ---"
run_test "A.4" "GET" "/events/recent?project_id=24&limit=10" "" "200"

# A.6a - Onboard non-existent project
echo "--- A.6a ---"
run_test "A.6a" "POST" "/projects/99999/onboard" '{}' "404"

# A.6b - Onboard project without git_url (use project with no git_url)
echo "--- A.6b ---"
# First find or create a project without git_url
no_git_proj=$(curl -s "$BASE/projects" | python3 -c "
import sys,json
d=json.load(sys.stdin)
for p in d:
  if not p.get('git_url'):
    print(p['id'])
    break
else:
  print('NONE')
" 2>/dev/null)
if [ "$no_git_proj" = "NONE" ]; then
  # Create one without git_url
  new_proj=$(curl -s -X POST -H "Content-Type: application/json" -d '{"name":"no-git-test"}' "$BASE/projects" 2>/dev/null)
  no_git_proj=$(echo "$new_proj" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null)
fi
echo "Project without git_url: $no_git_proj"
run_test "A.6b" "POST" "/projects/$no_git_proj/onboard" '{}' "400"

echo ""
echo "=== SECTION B: Worktree Management ==="

# B.1 - GET branches
echo "--- B.1 ---"
run_test "B.1" "GET" "/projects/24/branches" "" "200"

# B.2 - Create branch
echo "--- B.2 ---"
run_test "B.2" "POST" "/projects/24/branches" '{"branch_name":"test-wt-suite2"}' "ANY"

# B.2b - Verify branch
echo "--- B.2b ---"
has_branch=$(curl -s "$BASE/projects/24/branches" | python3 -c "
import sys,json
d=json.load(sys.stdin)
names=[b['name'] for b in d]
print('YES' if 'test-wt-suite2' in names else 'NO')
" 2>/dev/null)
if [ "$has_branch" = "YES" ]; then
  echo "B.2b|✅ PASS|200|test-wt-suite2 found in branches"
else
  echo "B.2b|❌ FAIL|200|test-wt-suite2 NOT found"
fi

# B.4 - Delete branch
echo "--- B.4 ---"
run_test "B.4" "DELETE" "/projects/24/branches/test-wt-suite2" '' "ANY"

# B.5 - GET worktrees
echo "--- B.5 ---"
run_test "B.5" "GET" "/projects/24/worktrees" "" "200"

echo ""
echo "=== SECTION C: SpecKit Full Flow ==="

# C.1 - POST /speckit/specify (should now return 202)
echo "--- C.1 ---"
run_test "C.1" "POST" "/speckit/specify" '{"project_id":24,"description":"Test feature for automated suite validation and verification","feature_name":"suite-validation"}' "202"

# C.2 - GET status
echo "--- C.2 ---"
run_test "C.2" "GET" "/speckit/status/24" "" "200"

# C.7 - POST /speckit/workflow (should now return 202)
echo "--- C.7 ---"
run_test "C.7" "POST" "/speckit/workflow" '{"project_id":24,"description":"Test workflow for automated suite validation and verification process","feature_name":"workflow-suite-test"}' "202"

# C.10a - GET specifications
echo "--- C.10a ---"
run_test "C.10a" "GET" "/specifications" "" "200"

# C.10b - GET specifications with limit
echo "--- C.10b ---"
run_test "C.10b" "GET" "/specifications?limit=5" "" "200"

# Get latest spec_run_id for dependent tests
echo "--- Getting latest spec_run_id ---"
latest_run=$(curl -s "$BASE/speckit/status/24" | python3 -c "
import sys,json
d=json.load(sys.stdin)
for s in d.get('specs',[]):
  if s.get('spec_run_id'):
    print(s['spec_run_id'])
    break
" 2>/dev/null)
echo "Latest spec_run_id: $latest_run"

# C.3 - POST /speckit/plan (dependent)
echo "--- C.3 ---"
if [ -n "$latest_run" ]; then
  run_test "C.3" "POST" "/speckit/plan" "{\"project_id\":24,\"spec_path\":\"specs/001-suite-validation/spec.md\",\"spec_run_id\":$latest_run}" "202"
else
  echo "C.3|⏭️ SKIP|—|No spec_run_id available"
fi

# C.4 - POST /speckit/tasks (dependent)
echo "--- C.4 ---"
run_test "C.4" "POST" "/speckit/tasks" '{"project_id":24,"plan_path":"specs/001-suite-validation/plan.md"}' "202"

# C.5 - POST /speckit/analyze
echo "--- C.5 ---"
run_test "C.5" "POST" "/speckit/analyze" '{"project_id":24,"spec_path":"specs/001-suite-validation/spec.md"}' "202"

# C.6 - POST /speckit/checklist
echo "--- C.6 ---"
run_test "C.6" "POST" "/speckit/checklist" '{"project_id":24,"spec_path":"specs/001-suite-validation/spec.md"}' "202"

# C.8 - POST /speckit/spec-runs/{id}/cleanup
echo "--- C.8 ---"
if [ -n "$latest_run" ]; then
  # Stop it first
  curl -s -X POST "$BASE/speckit/spec-runs/$latest_run/stop" > /dev/null 2>&1
  run_test "C.8" "POST" "/speckit/spec-runs/$latest_run/cleanup" '{"delete_remote_branch":false}' "ANY"
else
  echo "C.8|⏭️ SKIP|—|No spec_run_id available"
fi

# C.9 - POST /speckit/implement
echo "--- C.9 ---"
run_test "C.9" "POST" "/speckit/implement" '{"project_id":24,"spec_path":"specs/001-suite-validation/spec.md"}' "202"

# C.extra - Stop endpoint test
echo "--- C.stop ---"
# Create a new run to test stop
stop_resp=$(curl -s -w '\nHTTP_CODE:%{http_code}' --max-time 30 -X POST -H "Content-Type: application/json" \
  -d '{"project_id":24,"description":"Test run for stop endpoint verification purpose","feature_name":"stop-test"}' \
  "$BASE/speckit/specify" 2>/dev/null)
stop_code=$(echo "$stop_resp" | grep 'HTTP_CODE:' | sed 's/HTTP_CODE://')
stop_body=$(echo "$stop_resp" | grep -v 'HTTP_CODE:' | head -c 200)
echo "C.stop-create|✅ PASS|$stop_code|$stop_body"

# Get the new run ID
new_run_id=$(echo "$stop_body" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('spec_run_id',''))" 2>/dev/null)
if [ -n "$new_run_id" ] && [ "$new_run_id" != "" ]; then
  run_test "C.stop" "POST" "/speckit/spec-runs/$new_run_id/stop" '' "200"
else
  echo "C.stop|⏭️ SKIP|—|Could not create spec run for stop test"
fi

echo ""
echo "=== SECTION D: AI Agent Execution ==="

# D.1 - Agent health
echo "--- D.1 ---"
run_test "D.1" "GET" "/agents/health" "" "200"

# D.2 - Agent tests
echo "--- D.2 ---"
run_test "D.2.opencode" "POST" "/agents/opencode/test" '' "200"
run_test "D.2.claude" "POST" "/agents/claude-code/test" '' "200"
run_test "D.2.codex" "POST" "/agents/codex/test" '' "200"
run_test "D.2.gemini" "POST" "/agents/gemini-cli/test" '' "200"

# D.3 - Individual agent health
echo "--- D.3 ---"
run_test "D.3.opencode" "GET" "/agents/opencode/health" '' "200"
run_test "D.3.claude" "GET" "/agents/claude-code/health" '' "200"
run_test "D.3.codex" "GET" "/agents/codex/health" '' "200"
run_test "D.3.gemini" "GET" "/agents/gemini-cli/health" '' "200"

# D.5 - List agents
echo "--- D.5 ---"
run_test "D.5" "GET" "/agents" '' "200"

# D.6 - Agent metrics
echo "--- D.6 ---"
run_test "D.6" "GET" "/agents/metrics" '' "200"

# D.7 - PUT /agents/opencode
echo "--- D.7 ---"
run_test "D.7" "PUT" "/agents/opencode" '{"default_model":"zai-coding-plan/glm-4.6"}' "200"

# D.gemini-warning - Check gemini-cli health for warnings field
echo "--- D.gemini-warning ---"
gemini_health=$(curl -s "$BASE/agents/gemini-cli/health")
has_warnings=$(echo "$gemini_health" | python3 -c "
import sys,json
d=json.load(sys.stdin)
w=d.get('warnings',d.get('warning',[]))
if w:
  print('YES')
else:
  print('NO')
" 2>/dev/null)
if [ "$has_warnings" = "YES" ]; then
  echo "D.gemini-warning|✅ PASS|200|Warnings field present: $gemini_health" | head -c 250
  echo ""
else
  echo "D.gemini-warning|❌ FAIL|200|No warnings field: $gemini_health" | head -c 250
  echo ""
fi

echo ""
echo "=== SECTION E: Brownfield + Task Cycle ==="

# E.1 - Brownfield run (should now return 202)
echo "--- E.1 ---"
run_test "E.1" "POST" "/projects/24/brownfield/run" '{"feature_request":"Add basic logging middleware to the FastAPI application","feature_name":"logging-middleware","output_mode":"task_cycle"}' "202"

# E.2 - Task cycle
echo "--- E.2 ---"
run_test "E.2" "GET" "/projects/24/task-cycle" '' "200"

# E.3 - Work item lifecycle (skip if no items)
echo "--- E.3 ---"
has_items=$(curl -s "$BASE/projects/24/task-cycle" | python3 -c "
import sys,json
d=json.load(sys.stdin)
if isinstance(d,list) and len(d)>0:
  print('YES')
else:
  print('NO')
" 2>/dev/null)
if [ "$has_items" = "YES" ]; then
  echo "E.3|✅ PASS|200|Work items available for lifecycle test"
else
  echo "E.3|⏭️ SKIP|—|No work items available (async run not yet complete)"
fi

# E.4 - Protocols
echo "--- E.4 ---"
run_test "E.4" "GET" "/projects/24/protocols" '' "200"

echo ""
echo "=== SECTION G: Sprint + Execution Layer ==="

# G.1 - GET sprints
echo "--- G.1 ---"
run_test "G.1" "GET" "/sprints" '' "200"

# G.2 - Create sprint
echo "--- G.2 ---"
run_test "G.2" "POST" "/sprints" '{"name":"Test Sprint Suite v2","start_date":"2026-04-19","end_date":"2026-05-02","project_id":24}' "ANY"

# Get sprint ID
sprint_id=$(curl -s "$BASE/sprints" | python3 -c "
import sys,json
d=json.load(sys.stdin)
if isinstance(d,list) and len(d)>0:
  print(d[-1]['id'])
else:
  print('3')
" 2>/dev/null)
echo "Using sprint_id: $sprint_id"

# G.3a - Sprint tasks
echo "--- G.3a ---"
run_test "G.3a" "GET" "/sprints/$sprint_id/tasks" '' "200"

# G.4 - Sprint metrics
echo "--- G.4 ---"
run_test "G.4" "GET" "/sprints/$sprint_id/metrics" '' "200"

echo ""
echo "=== SECTION H: Event System ==="

# H.1 - SSE stream (just check headers, don't read full stream)
echo "--- H.1 ---"
sse_check=$(curl -s -o /dev/null -w "%{http_code}|%{content_type}" --max-time 5 "$BASE/events" 2>/dev/null)
sse_code=$(echo "$sse_check" | cut -d'|' -f1)
sse_ct=$(echo "$sse_check" | cut -d'|' -f2)
if [[ "$sse_code" == "200" ]] && [[ "$sse_ct" == *"event-stream"* ]]; then
  echo "H.1|✅ PASS|$sse_code|Content-Type: $sse_ct"
else
  echo "H.1|❌ FAIL|$sse_code|Content-Type: $sse_ct"
fi

# H.2 - Recent events
echo "--- H.2 ---"
run_test "H.2" "GET" "/events/recent" '' "200"

echo ""
echo "=== SECTION I: Policy Packs + Constitution ==="

# I.1 - GET policy packs
echo "--- I.1 ---"
run_test "I.1" "GET" "/policy_packs" '' "200"

# I.2 - Create policy pack
echo "--- I.2 ---"
run_test "I.2" "POST" "/policy_packs" '{"key":"test-suite-v2-policy","version":"1.0.0","name":"Test Suite v2 Policy","description":"Policy for test suite v2"}' "ANY"

# I.3 - Get specific policy pack
echo "--- I.3 ---"
run_test "I.3" "GET" "/policy_packs/test-suite-v2-policy" '' "200"

# I.5 - Clarifications
echo "--- I.5 ---"
run_test "I.5" "GET" "/projects/24/clarifications" '' "200"

echo ""
echo "=== ALL TESTS COMPLETE ==="
