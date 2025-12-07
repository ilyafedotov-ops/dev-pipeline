const state = {
  token: localStorage.getItem("df_token") || "",
  apiBase: localStorage.getItem("df_api_base") || "",
  projects: [],
  protocols: [],
  steps: [],
  events: [],
  operations: [],
  eventFilter: "all",
  eventSpecFilter: "",
  operationsInvalidOnly: false,
  operationsSpecFilter: "",
  projectSort: "name",
  protocolSort: "updated",
  projectTokens: JSON.parse(localStorage.getItem("df_project_tokens") || "{}"),
  queueStats: null,
  queueJobs: [],
  metrics: { qaVerdicts: {}, tokenUsageByPhase: {}, tokenUsageByModel: {} },
  selectedProject: null,
  selectedProtocol: null,
  poll: null,
};

// Rough price table (USD per 1k tokens). Extend as needed; unknown models default to 0.
const MODEL_PRICING = {
  "gpt-5.1-high": 0.003,
  "gpt-5.1": 0.002,
  "codex-5.1-max-xhigh": 0.02,
  "codex-5.1-max": 0.01,
};

const statusEl = document.getElementById("authStatus");
const apiBaseInput = document.getElementById("apiBase");
const apiTokenInput = document.getElementById("apiToken");
const projectTokenInput = document.getElementById("projectToken");
const saveProjectTokenBtn = document.getElementById("saveProjectToken");

function setStatus(message, level = "info") {
  if (!statusEl) return;
  statusEl.textContent = message;
  statusEl.style.color = level === "error" ? "#f87171" : "#7e8ba1";

  if (level === "toast") {
    statusEl.style.transition = "opacity 0.3s ease";
    statusEl.style.opacity = 1;
    setTimeout(() => {
      statusEl.style.opacity = 0.4;
    }, 1200);
  }
}

function apiPath(path) {
  const base = state.apiBase || "";
  const baseTrimmed = base.endsWith("/") ? base.slice(0, -1) : base;
  return `${baseTrimmed}${path}`;
}

function statusClass(status) {
  return `status-${(status || "").toLowerCase()}`;
}

async function apiFetch(path, options = {}) {
  const { projectId, ...restOptions } = options;
  const headers = restOptions.headers || {};
  if (state.token) {
    headers["Authorization"] = `Bearer ${state.token}`;
  }
  const targetProjectId = projectId || state.selectedProject;
  if (targetProjectId) {
    const projectToken = state.projectTokens[String(targetProjectId)];
    if (projectToken) {
      headers["X-Project-Token"] = projectToken;
    }
  }
  if (restOptions.body && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  const resp = await fetch(apiPath(path), { ...restOptions, headers });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`${resp.status} ${resp.statusText}: ${text}`);
  }
  const contentType = resp.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return resp.json();
  }
  return resp.text();
}

function persistAuth() {
  localStorage.setItem("df_token", state.token);
  localStorage.setItem("df_api_base", state.apiBase);
  apiBaseInput.value = state.apiBase;
  apiTokenInput.value = state.token;
  setStatus("Auth saved. Loading data...");
  loadProjects();
  loadOperations();
  loadQueue();
  loadMetrics();
}

function persistProjectTokens() {
  localStorage.setItem("df_project_tokens", JSON.stringify(state.projectTokens));
  if (state.selectedProject && projectTokenInput) {
    projectTokenInput.value = state.projectTokens[String(state.selectedProject)] || "";
  }
}

async function loadProjects() {
  try {
    const projects = await apiFetch("/projects");
    state.projects = projects;
    renderProjects();
    setStatus(`Loaded ${projects.length} project(s).`);
  } catch (err) {
    setStatus(err.message, "error");
  }
}

function renderProjects() {
  const container = document.getElementById("projectList");
  container.innerHTML = "";
  const sortBar = document.createElement("div");
  sortBar.className = "sort-toggle";
  sortBar.innerHTML = `
    <span>Sort projects by:</span>
    <button class="${state.projectSort === "name" ? "active" : ""}" data-sort="name">Name</button>
    <button class="${state.projectSort === "spec" ? "active" : ""}" data-sort="spec">Spec status</button>
  `;
  container.appendChild(sortBar);
  const sorted = [...state.projects].sort((a, b) => {
    if (state.projectSort === "name") {
      return a.name.localeCompare(b.name);
    }
    if (state.projectSort === "spec") {
      const aInvalid = (state.protocols || []).some((p) => p.project_id === a.id && p.spec_validation_status === "invalid");
      const bInvalid = (state.protocols || []).some((p) => p.project_id === b.id && p.spec_validation_status === "invalid");
      if (aInvalid !== bInvalid) return aInvalid ? -1 : 1;
      return a.name.localeCompare(b.name);
    }
    return a.id - b.id;
  });
  sorted.forEach((proj) => {
    const anyInvalid = (state.protocols || []).some((p) => p.project_id === proj.id && p.spec_validation_status === "invalid");
    const card = document.createElement("div");
    card.className = `card ${state.selectedProject === proj.id ? "active" : ""}`;
    card.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <div>
          <div>${proj.name}</div>
          <div class="muted" style="font-size:12px;">${proj.git_url}</div>
        </div>
        <div style="display:flex; gap:6px; align-items:center;">
          ${anyInvalid ? `<span class="pill spec-invalid">spec invalid</span>` : ""}
          <span class="pill">${proj.base_branch}</span>
        </div>
      </div>
    `;
    card.onclick = () => {
      if (state.poll) {
        clearInterval(state.poll);
        state.poll = null;
      }
      state.selectedProject = proj.id;
      state.selectedProtocol = null;
      state.steps = [];
      state.events = [];
      if (projectTokenInput) {
        projectTokenInput.value = state.projectTokens[String(proj.id)] || "";
      }
      renderProjects();
        loadProtocols();
        loadOperations();
      };
      container.appendChild(card);
    });
  container.querySelectorAll(".sort-toggle button[data-sort]").forEach((btn) => {
    btn.onclick = () => {
      state.projectSort = btn.getAttribute("data-sort");
      renderProjects();
    };
  });
}

async function loadProtocols() {
  if (!state.selectedProject) {
    document.getElementById("protocolList").innerHTML = `<p class="muted">Select a project to view runs.</p>`;
    document.getElementById("protocolDetail").innerHTML = "";
    return;
  }
  try {
    const runs = await apiFetch(`/projects/${state.selectedProject}/protocols`);
    state.protocols = runs;
    renderProtocols();
    setStatus(`Loaded ${runs.length} protocol run(s).`);
  } catch (err) {
    setStatus(err.message, "error");
  }
}

function renderProtocols() {
  const list = document.getElementById("protocolList");
  list.innerHTML = "";
  if (!state.protocols.length) {
    list.innerHTML = `<p class="muted">No protocol runs yet.</p>`;
  } else {
    const sortBar = document.createElement("div");
    sortBar.className = "sort-toggle";
    sortBar.innerHTML = `
      <span>Sort runs by:</span>
      <button class="${state.protocolSort === "updated" ? "active" : ""}" data-sort="updated">Updated</button>
      <button class="${state.protocolSort === "spec" ? "active" : ""}" data-sort="spec">Spec status</button>
    `;
    list.appendChild(sortBar);

    const sortedRuns = [...state.protocols].sort((a, b) => {
      if (state.protocolSort === "spec") {
        const rank = (run) => {
          const status = (run.spec_validation_status || "unknown").toLowerCase();
          if (status === "invalid") return 0;
          if (status === "unknown") return 1;
          if (status === "valid") return 2;
          return 3;
        };
        const diff = rank(a) - rank(b);
        if (diff !== 0) return diff;
      }
      const aTs = new Date(a.updated_at || 0).getTime() || 0;
      const bTs = new Date(b.updated_at || 0).getTime() || 0;
      if (bTs !== aTs) return bTs - aTs;
      return a.protocol_name.localeCompare(b.protocol_name);
    });

    const table = document.createElement("table");
    table.className = "table";
    table.innerHTML = `
      <thead>
        <tr>
          <th>Name</th>
          <th>Status</th>
          <th>Spec</th>
          <th>Updated</th>
        </tr>
      </thead>
      <tbody></tbody>
    `;
    const body = table.querySelector("tbody");
    sortedRuns.forEach((run) => {
      const row = document.createElement("tr");
      row.style.cursor = "pointer";
      const specStatus = (run.spec_validation_status || "unknown").toLowerCase();
      const badgeClass = specStatus === "valid" ? "spec-valid" : specStatus === "invalid" ? "spec-invalid" : "spec-unknown";
      const specBadge = run.spec_hash
        ? `<span class="pill ${badgeClass}">${run.spec_hash} · ${specStatus}</span>`
        : `<span class="pill spec-unknown">spec: n/a</span>`;
      row.innerHTML = `
        <td>${run.protocol_name}</td>
        <td><span class="pill ${statusClass(run.status)}">${run.status}</span></td>
        <td>${specBadge}</td>
        <td class="muted">${formatDate(run.updated_at)}</td>
      `;
      row.onclick = () => {
        state.selectedProtocol = run.id;
        renderProtocols();
        loadSteps();
        loadEvents();
        startPolling();
      };
      if (state.selectedProtocol === run.id) {
        row.style.background = "rgba(96,165,250,0.08)";
      }
      body.appendChild(row);
    });
    list.appendChild(table);

    sortBar.querySelectorAll("button[data-sort]").forEach((btn) => {
      btn.onclick = () => {
        state.protocolSort = btn.getAttribute("data-sort");
        renderProtocols();
      };
    });
  }
  renderProtocolDetail();
}

function renderProtocolDetail() {
  const container = document.getElementById("protocolDetail");
  if (!state.selectedProtocol) {
    container.innerHTML = `<p class="muted">Select a protocol run to see steps and events.</p>`;
    return;
  }
  const run = state.protocols.find((r) => r.id === state.selectedProtocol);
  if (!run) {
    container.innerHTML = `<p class="muted">Protocol not found.</p>`;
    return;
  }
  const latestStep = state.steps[state.steps.length - 1];
  container.innerHTML = `
    <div class="pane">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <div>
          <div style="font-weight:700;">${run.protocol_name}</div>
          <div class="muted">${run.description || ""}</div>
          ${renderTemplateMeta(run)}
        </div>
        <span class="pill ${statusClass(run.status)}">${run.status}</span>
      </div>
      <div class="actions">
        <button id="startRun" class="primary">Start planning</button>
        <button id="runNext">Run next step</button>
        <button id="retryStep">Retry failed step</button>
        <button id="runQa">Run QA on latest</button>
        <button id="approveStep">Approve latest</button>
        <button id="openPr">Open PR/MR now</button>
        <button id="pauseRun">Pause</button>
        <button id="resumeRun">Resume</button>
        <button id="cancelRun" class="danger">Cancel</button>
        <button id="refreshActive">Refresh</button>
      </div>
    </div>
    ${renderCiHints(run)}
    <div class="split">
      <div class="pane">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <h3>Steps</h3>
          <span class="muted">${state.steps.length} step(s)</span>
        </div>
        ${renderStepsTable()}
      </div>
      <div class="pane">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <div>
            <h3>Events</h3>
            <div class="muted small">${eventSummaryLabel()}</div>
          </div>
          <div class="button-group">
            ${["all", "loop", "trigger"].map((f) => `<button class="${state.eventFilter === f ? "primary" : ""}" data-filter="${f}">${f}</button>`).join(" ")}
            <input id="specFilterInput" class="input-inline" placeholder="spec hash" value="${state.eventSpecFilter || ""}" />
          </div>
        </div>
        ${renderEventsList()}
      </div>
    </div>
  `;

  document.getElementById("startRun").onclick = () => startProtocol(run.id);
  document.getElementById("pauseRun").onclick = () => pauseProtocol(run.id);
  document.getElementById("resumeRun").onclick = () => resumeProtocol(run.id);
  document.getElementById("cancelRun").onclick = () => cancelProtocol(run.id);
  document.getElementById("runNext").onclick = () => runNextStep(run.id);
  document.getElementById("retryStep").onclick = () => retryLatest(run.id);
  document.getElementById("runQa").onclick = () => runQaLatest();
  document.getElementById("approveStep").onclick = () => approveLatest();
  document.getElementById("openPr").onclick = () => openPr(run.id);
  document.getElementById("refreshActive").onclick = () => {
    loadSteps();
    loadEvents();
  };
  bindEventFilters();

  document.querySelectorAll("button[data-copy-spec]").forEach((btn) => {
    btn.onclick = async (e) => {
      const hash = e.currentTarget.getAttribute("data-copy-spec");
      try {
        await navigator.clipboard.writeText(hash);
        setStatus(`Copied spec hash ${hash}`, "toast");
        const existing = e.currentTarget.parentElement.querySelector(".tiny-toast");
        if (existing) {
          existing.remove();
        }
        const toast = document.createElement("span");
        toast.className = "tiny-toast";
        toast.textContent = "Copied!";
        e.currentTarget.insertAdjacentElement("afterend", toast);
        setTimeout(() => {
          toast.remove();
        }, 1500);
      } catch (err) {
        setStatus("Copy failed", "error");
      }
    };
  });

  const startBtn = document.getElementById("startRun");
  const pauseBtn = document.getElementById("pauseRun");
  const resumeBtn = document.getElementById("resumeRun");
  const cancelBtn = document.getElementById("cancelRun");
  const runNextBtn = document.getElementById("runNext");
  const retryBtn = document.getElementById("retryStep");
  const qaBtn = document.getElementById("runQa");
  const approveBtn = document.getElementById("approveStep");

  const terminal = ["completed", "cancelled", "failed"].includes(run.status);
  startBtn.disabled = !["pending", "planned"].includes(run.status);
  pauseBtn.disabled = !["running", "planning"].includes(run.status);
  resumeBtn.disabled = run.status !== "paused";
  cancelBtn.disabled = terminal;

  runNextBtn.disabled = terminal || run.status === "paused";
  retryBtn.disabled = terminal || run.status === "paused";
  qaBtn.disabled = terminal || run.status === "paused" || !latestStep;
  approveBtn.disabled = terminal || run.status === "paused" || !latestStep;
}

function renderTemplateMeta(run) {
  const cfg = run.template_config || {};
  const template = cfg.template || run.template_source || null;
  const parts = [];
  if (template) {
    const name = template.template || template.name || "template";
    const version = template.version ? `v${template.version}` : "";
    parts.push(`Template: ${name} ${version}`.trim());
  }
  if (run.spec_hash) {
    const status = (run.spec_validation_status || "unknown").toLowerCase();
    const ts = run.spec_validated_at ? formatDate(run.spec_validated_at) : "-";
    const badgeClass = status === "valid" ? "spec-valid" : status === "invalid" ? "spec-invalid" : "spec-unknown";
    parts.push(
      `<span class="pill ${badgeClass}">spec ${run.spec_hash} · ${status} · ${ts}</span>
       <button class="tiny-btn" data-copy-spec="${run.spec_hash}" title="Copy spec hash">⧉</button>`
    );
  }
  if (!parts.length) return "";
  return `<div class="muted" style="font-size:12px;">${parts.join(" · ")}</div>`;
}

function renderStepsTable() {
  if (!state.steps.length) {
    return `<p class="muted">No steps recorded for this run.</p>`;
  }
  const rows = state.steps
    .map(
      (s) => `
        <tr>
          <td>${s.step_index}</td>
          <td>${s.step_name}</td>
          <td><span class="pill ${statusClass(s.status)}">${s.status}</span></td>
          <td class="muted">${s.model || "-"}</td>
          <td class="muted">${s.engine_id || "-"}</td>
          <td class="muted">${policyLabel(s.policy)}</td>
          <td class="muted">${runtimeStateLabel(s.runtime_state)}</td>
          <td class="muted">${s.summary || "-"}</td>
        </tr>
      `
    )
    .join("");
  return `
    <table class="table">
      <thead>
        <tr><th>#</th><th>Name</th><th>Status</th><th>Model</th><th>Engine</th><th>Policy</th><th>State</th><th>Summary</th></tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function policyLabel(policy) {
  if (!policy) return "-";
  if (Array.isArray(policy) && policy.length) {
    return policy.map((p) => policyLabel(p)).join(" / ");
  }
  const parts = [];
  if (policy.behavior) parts.push(policy.behavior);
  if (policy.action) parts.push(policy.action);
  if (policy.trigger_agent_id) parts.push(`→${policy.trigger_agent_id}`);
  if (policy.max_iterations) parts.push(`max:${policy.max_iterations}`);
  return parts.join(" ");
}

function runtimeStateLabel(state) {
  if (!state) return "-";
  const parts = [];
  const loops = state.loop_counts || state.loopCounts;
  if (loops && typeof loops === "object") {
    const loopBits = Object.entries(loops).map(([k, v]) => `${k}:${v}`);
    if (loopBits.length) parts.push(`loops(${loopBits.join(",")})`);
  }
  if (state.last_triggered_by) parts.push(`triggered_by:${state.last_triggered_by}`);
  if (state.last_target_step_index !== undefined) parts.push(`target:${state.last_target_step_index}`);
  return parts.join(" ") || "-";
}

function eventTypeClass(eventType) {
  const important = [
    "loop_decision",
    "loop_limit_reached",
    "loop_condition_skipped",
    "trigger_decision",
    "trigger_enqueued",
    "trigger_executed_inline",
    "trigger_inline_depth_exceeded",
    "trigger_enqueue_failed",
    "trigger_condition_skipped",
    "trigger_missing_target",
  ];
  if (important.includes(eventType)) return "warn";
  return "";
}

function filteredEvents() {
  const filter = state.eventFilter || "all";
  if (filter === "loop") {
    return state.events.filter((e) => e.event_type && e.event_type.startsWith("loop_"));
  }
  if (filter === "trigger") {
    return state.events.filter((e) => e.event_type && e.event_type.startsWith("trigger_"));
  }
  const specFilter = (state.eventSpecFilter || "").trim().toLowerCase();
  const events = state.events;
  if (!specFilter) return events;
  return events.filter((e) => {
    const meta = e.metadata || {};
    const specHash = (meta.spec_hash || meta.specHash || "").toLowerCase();
    return specHash.includes(specFilter);
  });
}

function eventSummaryLabel() {
  const total = state.events.length;
  const loops = state.events.filter((e) => e.event_type && e.event_type.startsWith("loop_")).length;
  const triggers = state.events.filter((e) => e.event_type && e.event_type.startsWith("trigger_")).length;
  const parts = [`${total} total`, `loop:${loops}`, `trigger:${triggers}`];
  return parts.join(" · ");
}

function eventMetaSnippet(event) {
  const meta = event.metadata || {};
  const parts = [];
  if (event.event_type === "loop_decision" || event.event_type === "loop_limit_reached") {
    if (meta.target_step_index !== undefined) parts.push(`target:${meta.target_step_index}`);
    if (meta.iterations !== undefined) {
      const max = meta.max_iterations !== undefined ? `/${meta.max_iterations}` : "";
      parts.push(`iter:${meta.iterations}${max}`);
    }
    if (Array.isArray(meta.steps_reset)) parts.push(`reset:${meta.steps_reset.length}`);
  }
  if (event.event_type.startsWith("trigger_")) {
    if (meta.target_step_index !== undefined) parts.push(`target:${meta.target_step_index}`);
    if (meta.target_step_id !== undefined) parts.push(`id:${meta.target_step_id}`);
    if (meta.source) parts.push(`source:${meta.source}`);
    if (meta.reason) parts.push(`reason:${meta.reason}`);
    if (meta.policy && meta.policy.module_id) parts.push(`policy:${meta.policy.module_id}`);
  }
  return parts.join(" · ");
}

function renderEventsList() {
  const events = filteredEvents();
  if (!events.length) {
    return `<p class="muted">Events will appear as jobs run.</p>`;
  }
  return events
    .map(
      (e) => {
        const meta = e.metadata || {};
        const promptVersions = meta.prompt_versions || meta.promptVersions;
        const promptLine = promptVersions
          ? Object.entries(promptVersions)
              .map(([k, v]) => `${k}:${v}`)
              .join(" · ")
          : null;
        const modelLine = meta.model ? `model:${meta.model}` : null;
        const specLine = meta.spec_hash ? `spec:${meta.spec_hash}` : null;
        const extraLine = [promptLine, modelLine, specLine].filter(Boolean).join(" | ");
        const metaSnippet = eventMetaSnippet(e);
        return `
        <div class="event">
          <div style="display:flex; justify-content:space-between;">
            <span class="pill ${eventTypeClass(e.event_type)}">${e.event_type}</span>
            <span class="muted">${formatDate(e.created_at)}</span>
          </div>
          <div>${e.message}</div>
          ${extraLine ? `<div class="muted" style="font-size:12px;">${extraLine}</div>` : ""}
          ${metaSnippet ? `<div class="muted" style="font-size:12px;">${metaSnippet}</div>` : ""}
          ${e.metadata ? `<div class="muted" style="font-size:12px;">${JSON.stringify(e.metadata)}</div>` : ""}
        </div>
      `;
      }
    )
    .join("");
}

function renderCiHints(run) {
  const base = (state.apiBase || window.location.origin || "").replace(/\/$/, "");
  const githubUrl = `${base}/webhooks/github`;
  const gitlabUrl = `${base}/webhooks/gitlab`;
  return `
    <div class="pane">
      <div class="pane-heading">
        <h3>CI & Webhooks</h3>
        <span class="pill">${run.protocol_name}</span>
      </div>
      <p class="muted small">Report CI status from your pipeline or post a webhook manually.</p>
      <div class="code-block">DEKSDENFLOW_API_BASE=${base || "http://localhost:8011"}
scripts/ci/report.sh success
# on failure
scripts/ci/report.sh failure</div>
      <div class="muted small">GitHub: POST ${githubUrl} (X-GitHub-Event: status) · GitLab: POST ${gitlabUrl} (X-Gitlab-Event: Pipeline Hook)</div>
    </div>
  `;
}

async function loadSteps() {
  if (!state.selectedProtocol) return;
  try {
    const steps = await apiFetch(`/protocols/${state.selectedProtocol}/steps`);
    state.steps = steps;
    renderProtocolDetail();
  } catch (err) {
    setStatus(err.message, "error");
  }
}

async function loadEvents() {
  if (!state.selectedProtocol) return;
  try {
    const events = await apiFetch(`/protocols/${state.selectedProtocol}/events`);
    state.events = events;
    renderProtocolDetail();
  } catch (err) {
    setStatus(err.message, "error");
  }
}

async function loadQueue() {
  try {
    const stats = await apiFetch("/queues");
    const jobs = await apiFetch("/queues/jobs");
    state.queueStats = stats;
    state.queueJobs = jobs;
    renderQueue();
  } catch (err) {
    state.queueStats = null;
    state.queueJobs = [];
    renderQueue();
    setStatus(err.message, "error");
  }
}

async function loadMetrics() {
  try {
    const text = await apiFetch("/metrics");
    const qaVerdicts = {};
    const tokenUsageByPhase = {};
    const tokenUsageByModel = {};
    text
      .split("\n")
      .forEach((line) => {
        if (line.startsWith("qa_verdict_total")) {
          const match = line.match(/verdict="([^"]+)".*\s(\d+(?:\.\d+)?)/);
          if (match) {
            qaVerdicts[match[1]] = parseFloat(match[2]);
          }
        }
        if (line.startsWith("codex_token_estimated_total")) {
          const match = line.match(/phase="([^"]+)",model="([^"]+)".*\s(\d+(?:\.\d+)?)/);
          if (match) {
            const phase = match[1];
            const value = parseFloat(match[3]);
            tokenUsageByPhase[phase] = (tokenUsageByPhase[phase] || 0) + value;
            if (!tokenUsageByModel[phase]) tokenUsageByModel[phase] = {};
            tokenUsageByModel[phase][match[2]] = (tokenUsageByModel[phase][match[2]] || 0) + value;
          }
        }
      });
    state.metrics = { qaVerdicts, tokenUsageByPhase, tokenUsageByModel };
    renderMetrics();
  } catch (err) {
    state.metrics = { qaVerdicts: {}, tokenUsageByPhase: {}, tokenUsageByModel: {} };
    renderMetrics();
    setStatus(err.message, "error");
  }
}

function renderQueue() {
  const statsEl = document.getElementById("queueStats");
  const jobsEl = document.getElementById("queueJobs");
  if (!statsEl || !jobsEl) return;
  if (!state.queueStats) {
    statsEl.innerHTML = `<p class="muted">Queue stats will appear after loading.</p>`;
    jobsEl.innerHTML = `<p class="muted">No jobs loaded.</p>`;
    return;
  }
  const { backend, ...queues } = state.queueStats;
  const queueRows = Object.entries(queues)
    .map(
      ([name, data]) => `
        <div class="event">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <span class="pill">${name}</span>
            <span class="muted" style="font-size:12px;">${backend || ""}</span>
          </div>
          <div class="muted" style="font-size:12px;">queued ${data.queued} · started ${data.started} · finished ${data.finished} · failed ${data.failed}</div>
        </div>
      `
    )
    .join("");
  statsEl.innerHTML = queueRows || `<p class="muted">No queues reported.</p>`;

  const jobs = (state.queueJobs || []).slice(0, 6);
  jobsEl.innerHTML = jobs.length
    ? jobs
        .map(
          (job) => `
            <div class="event">
              <div style="display:flex; justify-content:space-between; align-items:center;">
                <span class="pill">${job.job_type}</span>
                <span class="pill ${statusClass(job.status)}">${job.status}</span>
              </div>
              <div class="muted" style="font-size:12px;">${job.job_id}</div>
            </div>
          `
        )
        .join("")
    : `<p class="muted">No jobs yet.</p>`;
}

function renderSparkline(values, dataset) {
  const series = Array.isArray(values) ? values : Object.values(values || {});
  const scale = dataset ? Object.values(dataset) : series;
  if (!series.length || !scale.length) return "";
  const max = Math.max(...scale);
  if (max <= 0) return "";
  const blocks = ["▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"];
  const bars = series
    .map((v) => {
      const idx = Math.min(blocks.length - 1, Math.floor((v / max) * (blocks.length - 1)));
      return blocks[idx];
    })
    .join("");
  return `<div class="muted small" aria-label="sparkline">${bars}</div>`;
}

function renderBar(value, max, label) {
  if (!max || max <= 0) return "";
  const pct = Math.min(100, Math.round((value / max) * 100));
  return `
    <div class="bar-track" aria-label="${label} ${pct}%">
      <div class="bar-fill" style="width:${pct}%;"></div>
      <span class="bar-label">${pct}%</span>
    </div>
  `;
}

function estimateCost(modelTokens) {
  const perModel = modelTokens || {};
  let total = 0;
  const unknown = [];
  Object.entries(perModel).forEach(([model, tokens]) => {
    const price = MODEL_PRICING[model];
    if (price === undefined) {
      unknown.push(model);
      return;
    }
    total += (tokens / 1000) * price;
  });
  return { total, unknown };
}

function renderMetrics() {
  const target = document.getElementById("metricsSummary");
  if (!target) return;
  const qaVerdicts = state.metrics.qaVerdicts || {};
  const verdictKeys = Object.keys(qaVerdicts);
  const passCount = qaVerdicts.pass || qaVerdicts.PASS || 0;
  const failCount = qaVerdicts.fail || qaVerdicts.FAIL || 0;
  const totalQa = passCount + failCount;
  const passRate = totalQa ? Math.round((passCount / totalQa) * 100) : null;

  const qaRows = verdictKeys.length
    ? verdictKeys
        .map(
          (key) => `
        <div class="event">
          <div style="display:flex; justify-content:space-between;">
            <span class="pill">${key}</span>
            <span class="muted">${qaVerdicts[key]}</span>
          </div>
          ${renderBar(qaVerdicts[key], totalQa, "qa")}
        </div>
      `
        )
        .join("")
    : `<p class="muted">QA metrics not yet available. Trigger QA to see verdict counts.</p>`;

  const tokenUsage = state.metrics.tokenUsageByPhase || {};
  const tokenModels = state.metrics.tokenUsageByModel || {};
  const tokenRows = Object.keys(tokenUsage).length
    ? Object.entries(tokenUsage)
        .map(([phase, value]) => {
          const costInfo = estimateCost(tokenModels[phase] || {});
          return `
        <div class="event">
          <div style="display:flex; justify-content:space-between;">
            <span class="pill">${phase}</span>
            <span class="muted">${Math.round(value)} tok${costInfo.total > 0 ? ` · ~$${costInfo.total.toFixed(2)}` : ""}</span>
          </div>
          ${renderBar(value, Math.max(...Object.values(tokenUsage)), "tokens")}
          ${costInfo.unknown.length ? `<div class="muted small">Unknown pricing for: ${costInfo.unknown.join(", ")}</div>` : ""}
        </div>
      `;
        })
        .join("")
    : `<p class="muted">Token usage metrics not yet available.</p>`;

  target.innerHTML = `
    <div>
      <div class="pane-heading" style="display:flex; justify-content:space-between; align-items:center;">
        <h4>QA verdicts</h4>
        <span class="muted small">/metrics</span>
      </div>
      ${passRate !== null ? `<div class="muted small">Pass rate: ${passRate}% (${passCount}/${totalQa})</div>` : ""}
      ${qaRows}
      <div class="pane-heading" style="display:flex; justify-content:space-between; align-items:center; margin-top:8px;">
        <h4>Token usage (estimated)</h4>
      </div>
      ${tokenRows}
    </div>
  `;
}

async function loadOperations() {
  const target = document.getElementById("operationsList");
  if (!target) return;
  try {
    const params = [];
    if (state.selectedProject) {
      params.push(`project_id=${state.selectedProject}`);
    }
    params.push("limit=50");
    const qs = params.length ? `?${params.join("&")}` : "";
    const events = await apiFetch(`/events${qs}`);
    state.operations = events;
    renderOperations();
  } catch (err) {
    state.operations = [];
    renderOperations();
    setStatus(err.message, "error");
  }
}

function renderOperations() {
  const target = document.getElementById("operationsList");
  if (!target) return;
  if (!state.operations.length) {
    target.innerHTML = `<p class="muted">Recent events will appear here.</p>`;
    return;
  }
  const toggle = `
    <div style="display:flex; justify-content:flex-end; align-items:center; gap:8px; margin-bottom:6px;">
      <label class="muted small" style="display:flex; align-items:center; gap:6px;">
        <input type="checkbox" id="opsInvalidOnly" ${state.operationsInvalidOnly ? "checked" : ""} />
        invalid specs only
      </label>
      <input id="opsSpecFilter" class="input-inline" placeholder="spec hash" value="${state.operationsSpecFilter || ""}" />
    </div>
  `;
  const filteredOps = state.operations.filter((e) => {
    if (!state.operationsInvalidOnly) return true;
    const meta = e.metadata || {};
    const status = meta.spec_status || meta.specStatus || null;
    if (status) return status === "invalid";
    const hash = meta.spec_hash || null;
    return Boolean(hash);
  });
  const specFilter = (state.operationsSpecFilter || "").trim().toLowerCase();
  const filteredBySpec = specFilter
    ? filteredOps.filter((e) => {
        const meta = e.metadata || {};
        const specHash = (meta.spec_hash || meta.specHash || "").toLowerCase();
        return specHash.includes(specFilter);
      })
    : filteredOps;
  target.innerHTML =
    toggle +
    filteredBySpec
      .slice(0, 40)
      .map((e) => {
        const meta = e.metadata || {};
        const specHash = meta.spec_hash || (meta.outputs && meta.outputs.spec_hash);
        const specStatus = meta.spec_status || meta.specStatus || "unknown";
        const contextBits = [
          e.project_name || e.project_id || "",
          e.protocol_name || "",
          e.step_run_id ? `step ${e.step_run_id}` : "",
        ]
          .filter(Boolean)
          .join(" · ");
        const specClass = specStatus === "valid" ? "spec-valid" : specStatus === "invalid" ? "spec-invalid" : "spec-unknown";
        const specPill = specHash ? `<span class="pill ${specClass}" style="margin-right:6px;">spec ${specHash}</span>` : "";
        return `
          <div class="event">
            <div style="display:flex; justify-content:space-between;">
              <span class="pill">${e.event_type}</span>
              <span class="muted">${formatDate(e.created_at)}</span>
            </div>
            <div>${specPill}${e.message}</div>
            ${contextBits ? `<div class="muted small">${contextBits}</div>` : ""}
            ${e.metadata ? `<div class="muted" style="font-size:12px;">${JSON.stringify(e.metadata)}</div>` : ""}
          </div>
        `;
      })
      .join("");
  const toggleEl = document.getElementById("opsInvalidOnly");
  if (toggleEl) {
    toggleEl.onchange = (e) => {
      state.operationsInvalidOnly = e.target.checked;
      renderOperations();
    };
  }
  const specInput = document.getElementById("opsSpecFilter");
  if (specInput) {
    specInput.oninput = (e) => {
      state.operationsSpecFilter = e.target.value;
      renderOperations();
    };
  }
}

function startPolling() {
  if (state.poll) {
    clearInterval(state.poll);
  }
  state.poll = setInterval(() => {
    loadSteps();
    loadEvents();
    loadOperations();
    loadMetrics();
  }, 4000);
}

function bindEventFilters() {
  document.querySelectorAll(".button-group button[data-filter]").forEach((btn) => {
    btn.onclick = () => {
      state.eventFilter = btn.getAttribute("data-filter");
      renderProtocolDetail();
    };
  });
  const specInput = document.getElementById("specFilterInput");
  if (specInput) {
    specInput.oninput = (e) => {
      state.eventSpecFilter = e.target.value;
      renderProtocolDetail();
    };
  }
}

async function startProtocol(runId) {
  try {
    await apiFetch(`/protocols/${runId}/actions/start`, { method: "POST" });
    setStatus("Planning enqueued.");
    loadEvents();
  } catch (err) {
    setStatus(err.message, "error");
  }
}

async function pauseProtocol(runId) {
  try {
    await apiFetch(`/protocols/${runId}/actions/pause`, { method: "POST" });
    setStatus("Protocol paused.");
    loadProtocols();
  } catch (err) {
    setStatus(err.message, "error");
  }
}

async function resumeProtocol(runId) {
  try {
    await apiFetch(`/protocols/${runId}/actions/resume`, { method: "POST" });
    setStatus("Protocol resumed.");
    loadProtocols();
  } catch (err) {
    setStatus(err.message, "error");
  }
}

async function cancelProtocol(runId) {
  try {
    await apiFetch(`/protocols/${runId}/actions/cancel`, { method: "POST" });
    setStatus("Protocol cancelled.");
    loadProtocols();
  } catch (err) {
    setStatus(err.message, "error");
  }
}

async function runNextStep(runId) {
  try {
    await apiFetch(`/protocols/${runId}/actions/run_next_step`, { method: "POST" });
    setStatus("Next step enqueued.");
    loadEvents();
  } catch (err) {
    setStatus(err.message, "error");
  }
}

async function retryLatest(runId) {
  try {
    await apiFetch(`/protocols/${runId}/actions/retry_latest`, { method: "POST" });
    setStatus("Retry enqueued.");
    loadEvents();
  } catch (err) {
    setStatus(err.message, "error");
  }
}

async function runQaLatest() {
  if (!state.steps.length) {
    setStatus("No steps to QA.", "error");
    return;
  }
  const latest = state.steps[state.steps.length - 1];
  try {
    await apiFetch(`/steps/${latest.id}/actions/run_qa`, { method: "POST" });
    setStatus(`QA enqueued for ${latest.step_name}.`);
    loadEvents();
  } catch (err) {
    setStatus(err.message, "error");
  }
}

async function approveLatest() {
  if (!state.steps.length) {
    setStatus("No steps to approve.", "error");
    return;
  }
  const latest = state.steps[state.steps.length - 1];
  try {
    await apiFetch(`/steps/${latest.id}/actions/approve`, { method: "POST" });
    setStatus(`Step ${latest.step_name} approved.`);
    loadSteps();
    loadEvents();
  } catch (err) {
    setStatus(err.message, "error");
  }
}

async function openPr(runId) {
  try {
    await apiFetch(`/protocols/${runId}/actions/open_pr`, { method: "POST" });
    setStatus("PR/MR job enqueued.");
    loadEvents();
  } catch (err) {
    setStatus(err.message, "error");
  }
}

function wireForms() {
  document.getElementById("saveAuth").onclick = () => {
    state.apiBase = apiBaseInput.value.trim();
    state.token = apiTokenInput.value.trim();
    persistAuth();
  };

  document.getElementById("refreshProjects").onclick = loadProjects;
  document.getElementById("refreshProtocols").onclick = loadProtocols;
  const refreshQueueBtn = document.getElementById("refreshQueue");
  if (refreshQueueBtn) {
    refreshQueueBtn.onclick = loadQueue;
  }
  const refreshOpsBtn = document.getElementById("refreshOperations");
  if (refreshOpsBtn) {
    refreshOpsBtn.onclick = loadOperations;
  }
  const refreshMetricsBtn = document.getElementById("refreshMetrics");
  if (refreshMetricsBtn) {
    refreshMetricsBtn.onclick = loadMetrics;
  }
  if (saveProjectTokenBtn) {
    saveProjectTokenBtn.onclick = () => {
      if (!state.selectedProject) {
        setStatus("Select a project first.", "error");
        return;
      }
      const token = projectTokenInput.value.trim();
      const key = String(state.selectedProject);
      if (token) {
        state.projectTokens[key] = token;
      } else {
        delete state.projectTokens[key];
      }
      persistProjectTokens();
      setStatus(token ? "Project token saved." : "Project token cleared.");
    };
  }

  document.getElementById("projectForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const form = e.target;
    const payload = {
      name: form.name.value,
      git_url: form.git_url.value,
      base_branch: form.base_branch.value || "main",
      ci_provider: form.ci_provider.value || null,
      default_models: parseJsonField(form.default_models.value),
    };
    try {
      await apiFetch("/projects", { method: "POST", body: JSON.stringify(payload) });
      setStatus("Project created and setup enqueued.");
      form.reset();
      loadProjects();
    } catch (err) {
      setStatus(err.message, "error");
    }
  });

  document.getElementById("protocolForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!state.selectedProject) {
      setStatus("Select a project first.", "error");
      return;
    }
    const form = e.target;
    const payload = {
      protocol_name: form.protocol_name.value,
      status: "planning",
      base_branch: form.base_branch.value || "main",
      worktree_path: null,
      protocol_root: null,
      description: form.description.value,
    };
    try {
      const run = await apiFetch(`/projects/${state.selectedProject}/protocols`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      await apiFetch(`/protocols/${run.id}/actions/start`, { method: "POST" });
      setStatus("Protocol created; planning enqueued.");
      form.reset();
      loadProtocols();
    } catch (err) {
      setStatus(err.message, "error");
    }
  });
}

function parseJsonField(value) {
  if (!value) return null;
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
}

function formatDate(dateString) {
  if (!dateString) return "";
  const d = new Date(dateString);
  if (Number.isNaN(d.getTime())) return dateString;
  return d.toLocaleString();
}

function init() {
  apiBaseInput.value = state.apiBase;
  apiTokenInput.value = state.token;
  renderQueue();
  renderOperations();
  renderMetrics();
  wireForms();
  if (state.token) {
    setStatus("Using saved token.");
    loadProjects();
    loadQueue();
    loadMetrics();
  } else {
    setStatus("Add a bearer token to start.");
  }
}

document.addEventListener("DOMContentLoaded", init);
