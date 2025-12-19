# SpecKit Full-Feature Alignment Execution Plan

## Scope
- Replace template-only SpecKit behavior with upstream SpecKit command flow.
- Align backend, frontend, and Windmill to the same SpecKit artifacts and statuses.
- Preserve existing DevGodzilla orchestration while adopting SpecKit structure, templates, and QA gates.

## Assumptions
- Upstream SpecKit sources are vendored under `Origins/spec-kit` and should not be edited directly.
- SpecKit artifacts follow upstream behavior (templates, commands, scripts, specs layout).
- No legacy fallback is required; use the single canonical `specs/` layout.

## Definition of Done
- SpecKit commands supported: constitution, specify, clarify, plan, checklist, tasks, analyze, implement.
- Artifacts are generated in a single canonical layout and surfaced in API/UI/Windmill consistently.
- QA gates consume SpecKit checklist outputs and constitution rules.
- No legacy fallback; canonical `specs/` only.

---

## Phase 1: Audit and Gap Map
**Owner:** Tech Lead/Architect  
**Milestone:** Gap map + decision log signed off  
**Estimate:** 2-3 person-days  

- [ ] P1-1 Inventory upstream SpecKit assets (templates, commands, scripts, memory).  
  Owner: Backend Lead | Est: 0.5d
- [ ] P1-2 Run SpecKit init in a scratch repo to capture actual output layout.  
  Owner: Backend Lead | Est: 0.5d
- [ ] P1-3 Map current DevGodzilla usage (API/CLI/Frontend/Windmill) vs upstream.  
  Owner: Tech Lead | Est: 1d
- [ ] P1-4 Confirm canonical spec artifact layout (`specs/`).  
  Owner: Tech Lead | Est: 0.5d

---

## Phase 2: Engine + Asset Integration
**Owner:** Backend Lead  
**Milestone:** SpecKit assets + execution adapter live (init/specify/plan/tasks)  
**Estimate:** 5-8 person-days  

- [ ] P2-1 Add SpecKit asset sync (templates, commands, scripts, memory).  
  Owner: Backend Lead | Est: 1d
- [ ] P2-2 Implement SpecKit execution adapter (library/CLI) with structured outputs.  
  Owner: Backend Lead | Est: 2d
- [ ] P2-3 Wire `init` to SpecKit adapter (fail fast if missing).  
  Owner: Backend Lead | Est: 0.5d
- [ ] P2-4 Update `run_specify/plan/tasks` to call SpecKit adapter.  
  Owner: Backend Lead | Est: 1.5d
- [ ] P2-5 Add `clarify/checklist/analyze/implement` primitives to service layer.  
  Owner: Backend Lead | Est: 1.5d
- [ ] P2-6 Align spec artifacts + metadata schema (paths, statuses, versioning).  
  Owner: Backend Lead | Est: 1d

---

## Phase 3: API + Data Model Alignment
**Owner:** Backend/API Lead  
**Milestone:** Full SpecKit API surface + typed models  
**Estimate:** 4-6 person-days  

- [ ] P3-1 Add `/speckit/clarify` endpoint and response schema.  
  Owner: Backend/API Lead | Est: 0.5d
- [ ] P3-2 Add `/speckit/checklist` endpoint and response schema.  
  Owner: Backend/API Lead | Est: 0.5d
- [ ] P3-3 Add `/speckit/analyze` endpoint and response schema.  
  Owner: Backend/API Lead | Est: 0.5d
- [ ] P3-4 Add `/speckit/implement` endpoint + run tracking.  
  Owner: Backend/API Lead | Est: 1d
- [ ] P3-5 Persist SpecKit metadata in DB (artifact paths, results, versions).  
  Owner: Backend/API Lead | Est: 1d
- [ ] P3-6 Update OpenAPI and docs for new endpoints.  
  Owner: Backend/API Lead | Est: 0.5d

---

## Phase 4: QA / Governance Integration
**Owner:** QA/Platform  
**Milestone:** QA gates powered by SpecKit outputs  
**Estimate:** 2-3 person-days  

- [ ] P4-1 Ingest SpecKit checklist into `ChecklistGate`.  
  Owner: QA/Platform | Est: 1d
- [ ] P4-2 Validate constitution compliance with SpecKit constitution content.  
  Owner: QA/Platform | Est: 1d
- [ ] P4-3 Add QA summaries to protocol/step APIs.  
  Owner: QA/Platform | Est: 0.5d

---

## Phase 5: Frontend Alignment
**Owner:** Frontend Lead  
**Milestone:** UI supports full SpecKit pipeline  
**Estimate:** 5-8 person-days  

- [ ] P5-1 Extend API hooks for clarify/checklist/analyze/implement.  
  Owner: Frontend Lead | Est: 1d
- [ ] P5-2 Update workflow UI to include new stages and statuses.  
  Owner: Frontend Lead | Est: 1.5d
- [ ] P5-3 Add views for clarify questions + checklist results + analyze report.  
  Owner: Frontend Lead | Est: 2d
- [ ] P5-4 Add implement run status/logs view.  
  Owner: Frontend Lead | Est: 1.5d
- [ ] P5-5 Update spec list/detail pages to show new artifacts.  
  Owner: Frontend Lead | Est: 1d

---

## Phase 6: Windmill Alignment
**Owner:** Windmill/Automation Owner  
**Milestone:** Windmill flows execute full SpecKit pipeline  
**Estimate:** 3-5 person-days  
a,d 
- [ ] P6-1 Add Windmill scripts for clarify/checklist/analyze/implement.  
  Owner: Windmill Owner | Est: 1d
- [ ] P6-2 Update flows to include new steps and outputs.  
  Owner: Windmill Owner | Est: 1.5d
- [ ] P6-3 Update Windmill apps to show new statuses/results.  
  Owner: Windmill Owner | Est: 1d
- [ ] P6-4 Add failure handling + retries for long-running steps.  
  Owner: Windmill Owner | Est: 0.5d

---

## Phase 7: Migration and Compatibility (removed)
No migration or compatibility layer is required. Use the single canonical `specs/` layout.

---

## Phase 8: Tests and Docs
**Owner:** QA + Docs  
**Milestone:** Test coverage + docs complete  
**Estimate:** 3-5 person-days  

- [ ] P8-1 Add unit tests for SpecKit adapter and artifact parsing.  
  Owner: QA | Est: 1d
- [ ] P8-2 Add integration tests for full pipeline.  
  Owner: QA | Est: 1.5d
- [ ] P8-3 Update API/CLI docs and onboarding guide.  
  Owner: Docs | Est: 1d
- [ ] P8-4 Add migration FAQ and troubleshooting.  
  Owner: Docs | Est: 0.5d

---

## Implementation Start (Now)
- [ ] Begin P2-1: SpecKit asset sync scaffolding (templates/commands/scripts/memory).
- [ ] Validate single canonical spec layout (`specs/`) is enforced end-to-end.
