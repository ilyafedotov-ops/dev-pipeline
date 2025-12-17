import { useCallback, useEffect, useState } from "react";
import "./App.css";
import "./components.css";
import { OpenAPI } from "windmill-client";
import { executeWorkspaceScript, token } from "./utils";

// Import new components
import { TaskDAGViewer } from "./components/core/TaskDAGViewer";
import { AgentSelector, AgentBadge } from "./components/core/AgentSelector";
import { QADashboard } from "./components/core/QADashboard";
import { SpecificationEditor } from "./components/core/SpecificationEditor";
import { FeedbackPanel } from "./components/workflow/FeedbackPanel";
import { UserStoryTracker } from "./components/workflow/UserStoryTracker";
import { JobsMonitor } from "./components/workflow/JobsMonitor";
import { ProjectOnboarding } from "./components/config/ProjectOnboarding";
import { AgentConfigManager } from "./components/config/AgentConfigManager";
import { Tabs, Modal } from "./components/common";
import type { Task, DAGDefinition, StepStatus } from "./types";

// Types
interface Project {
  id: number;
  name: string;
  description?: string;
  git_url?: string;
  base_branch: string;
  local_path?: string;
  status?: string;
  constitution_version?: string;
  created_at?: string;
  updated_at?: string;
}

interface Protocol {
  id: number;
  protocol_name: string;
  project_id: number;
  status: string;
  summary?: string;
  base_branch?: string;
  created_at: string;
}

interface Step {
  id: number;
  step_name: string;
  step_type: string;
  step_index: number;
  status: string;
  depends_on?: number[];
  parallel_group?: string;
  assigned_agent?: string;
  summary?: string;
}

interface Clarification {
  id: number;
  question: string;
  status: string;
  protocol_run_id: number;
  options?: string[];
  answer?: string;
  created_at: string;
}

interface Stats {
  total: number;
  running: number;
  completed_today: number;
}

OpenAPI.TOKEN = token;

// Status Badge Component - Windmill aligned
function StatusBadge({ status }: { status: string }) {
  const getClasses = (s: string) => {
    switch (s) {
      case 'active':
      case 'completed':
        return 'wm-badge wm-badge-success';
      case 'running':
        return 'wm-badge wm-badge-info';
      case 'pending':
        return 'wm-badge wm-badge-neutral';
      case 'failed':
        return 'wm-badge wm-badge-error';
      case 'archived':
        return 'wm-badge wm-badge-neutral';
      case 'open':
        return 'wm-badge wm-badge-warning';
      case 'answered':
        return 'wm-badge wm-badge-success';
      default:
        return 'wm-badge wm-badge-neutral';
    }
  };

  return <span className={getClasses(status)}>{status}</span>;
}

// Dashboard Component
function Dashboard({ onNavigate }: { onNavigate: (view: string, id?: number) => void }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [protocols, setProtocols] = useState<Protocol[]>([]);
  const [stats, setStats] = useState<Stats>({ total: 0, running: 0, completed_today: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [projectsResult, protocolsResult] = await Promise.all([
        executeWorkspaceScript("u/devgodzilla/list_projects", {}),
        executeWorkspaceScript("u/devgodzilla/list_protocols", {}),
      ]);
      setProjects(projectsResult?.projects || []);
      setProtocols(protocolsResult?.protocols || []);
      setStats(protocolsResult?.stats || { total: 0, running: 0, completed_today: 0 });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const activeProjects = projects.filter(p => p.status === 'active' || !p.status).length;
  const archivedProjects = projects.filter(p => p.status === 'archived').length;

  return (
    <div style={{ maxWidth: '80rem', margin: '0 auto', padding: '1.5rem 1rem' }}>
      <div className="page-header">
        <h1 className="page-title">DevGodzilla Dashboard</h1>
        <p className="page-subtitle">Manage your AI-driven development projects and protocols.</p>
      </div>

      {error && <div className="error-state" style={{ marginBottom: '1.5rem' }}>{error}</div>}

      {/* Stats Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1.5rem', marginBottom: '2rem' }}>
        <div className="stat-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <p className="stat-label">Total Projects</p>
              <p className="stat-value stat-value-frost">{projects.length}</p>
            </div>
            <span style={{ fontSize: '1.5rem' }}>📁</span>
          </div>
        </div>

        <div className="stat-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <p className="stat-label">Active Protocols</p>
              <p className="stat-value stat-value-frost">{stats.running}</p>
            </div>
            <span style={{ fontSize: '1.5rem' }}>⚡</span>
          </div>
        </div>

        <div className="stat-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <p className="stat-label">Completed Today</p>
              <p className="stat-value stat-value-success">{stats.completed_today}</p>
            </div>
            <span style={{ fontSize: '1.5rem' }}>✅</span>
          </div>
        </div>

        <div className="stat-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <p className="stat-label">Active / Archived</p>
              <p className="stat-value stat-value-neutral">{activeProjects} / {archivedProjects}</p>
            </div>
            <span style={{ fontSize: '1.5rem' }}>📦</span>
          </div>
        </div>
      </div>

      {/* Main Content Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '1.5rem' }}>
        {/* Recent Projects */}
        <div className="wm-card">
          <div style={{ padding: '1rem 1.5rem', borderBottom: '1px solid rgb(var(--color-surface-hover))', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600 }}>Recent Projects</h3>
            <button onClick={() => onNavigate('projects')} style={{ background: 'none', border: 'none', color: 'var(--frost-500)', fontSize: '0.875rem', cursor: 'pointer' }}>
              View all →
            </button>
          </div>
          <div>
            {loading ? (
              <div className="loading-state">Loading...</div>
            ) : projects.length === 0 ? (
              <div className="empty-state">No projects yet</div>
            ) : (
              projects.slice(0, 5).map(project => (
                <div
                  key={project.id}
                  onClick={() => onNavigate('project', project.id)}
                  className="list-item-hover"
                  style={{ padding: '0.75rem 1.5rem', cursor: 'pointer', borderBottom: '1px solid rgb(var(--color-surface-hover))' }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <p style={{ margin: 0, fontWeight: 500 }}>{project.name}</p>
                      <p style={{ margin: '0.25rem 0 0', fontSize: '0.875rem', color: 'rgb(var(--color-text-tertiary))' }}>{project.git_url || 'No repository'}</p>
                    </div>
                    <StatusBadge status={project.status || 'active'} />
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Recent Protocols */}
        <div className="wm-card">
          <div style={{ padding: '1rem 1.5rem', borderBottom: '1px solid rgb(var(--color-surface-hover))', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600 }}>Recent Protocols</h3>
            <button onClick={() => onNavigate('protocols')} style={{ background: 'none', border: 'none', color: 'var(--frost-500)', fontSize: '0.875rem', cursor: 'pointer' }}>
              View all →
            </button>
          </div>
          <div>
            {loading ? (
              <div className="loading-state">Loading...</div>
            ) : protocols.length === 0 ? (
              <div className="empty-state">No protocols yet</div>
            ) : (
              protocols.slice(0, 5).map(protocol => (
                <div
                  key={protocol.id}
                  onClick={() => onNavigate('protocol', protocol.id)}
                  className="list-item-hover"
                  style={{ padding: '0.75rem 1.5rem', cursor: 'pointer', borderBottom: '1px solid rgb(var(--color-surface-hover))' }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <p style={{ margin: 0, fontWeight: 500 }}>{protocol.protocol_name}</p>
                      <p style={{ margin: '0.25rem 0 0', fontSize: '0.875rem', color: 'rgb(var(--color-text-tertiary))' }}>
                        {protocol.created_at ? new Date(protocol.created_at).toLocaleDateString() : '—'}
                      </p>
                    </div>
                    <StatusBadge status={protocol.status} />
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div style={{ marginTop: '2rem' }}>
        <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem' }}>Quick Actions</h3>
        <div className="btn-group">
          <button onClick={() => onNavigate('create-project')} className="wm-btn-primary">
            ➕ New Project
          </button>
          <button onClick={() => onNavigate('clarifications')} className="wm-btn-secondary" style={{ background: '#fef3c7', borderColor: '#f59e0b', color: '#92400e' }}>
            ❓ Clarifications
          </button>
          <button onClick={loadData} className="wm-btn-secondary">
            🔄 Refresh
          </button>
        </div>
      </div>
    </div>
  );
}

// Projects List Component
function ProjectsList({ onNavigate }: { onNavigate: (view: string, id?: number) => void }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<string>("all");

  const loadProjects = useCallback(async () => {
    setLoading(true);
    try {
      const result = await executeWorkspaceScript("u/devgodzilla/list_projects", {});
      setProjects(result?.projects || []);
    } catch (e) {
      console.error("Failed to load projects:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  const filteredProjects = projects.filter(p => {
    const matchesSearch = !search ||
      p.name.toLowerCase().includes(search.toLowerCase()) ||
      p.description?.toLowerCase().includes(search.toLowerCase());

    const matchesFilter = filter === 'all' ||
      (filter === 'active' && (p.status === 'active' || !p.status)) ||
      (filter === 'archived' && p.status === 'archived');

    return matchesSearch && matchesFilter;
  });

  const stats = {
    total: projects.length,
    active: projects.filter(p => p.status === 'active' || !p.status).length,
    archived: projects.filter(p => p.status === 'archived').length,
  };

  return (
    <div style={{ maxWidth: '80rem', margin: '0 auto', padding: '1.5rem 1rem' }}>
      <button onClick={() => onNavigate('dashboard')} className="back-link">← Back to Dashboard</button>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <h1 className="page-title">Projects</h1>
        <button onClick={() => onNavigate('create-project')} className="wm-btn-primary">➕ New Project</button>
      </div>

      {/* Stats Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem', marginBottom: '1.5rem' }}>
        {[
          { label: 'Total', value: stats.total, filterValue: 'all' },
          { label: 'Active', value: stats.active, filterValue: 'active' },
          { label: 'Archived', value: stats.archived, filterValue: 'archived' },
        ].map(stat => (
          <button
            key={stat.filterValue}
            onClick={() => setFilter(stat.filterValue)}
            className="stat-card"
            style={{
              textAlign: 'left',
              cursor: 'pointer',
              border: filter === stat.filterValue ? '2px solid var(--frost-500)' : undefined
            }}
          >
            <p className="stat-value stat-value-frost">{stat.value}</p>
            <p className="stat-label">{stat.label}</p>
          </button>
        ))}
      </div>

      {/* Search */}
      <div style={{ marginBottom: '1rem' }}>
        <input
          type="text"
          placeholder="🔍 Search projects..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="form-input"
        />
      </div>

      {/* Table */}
      {loading ? (
        <div className="loading-state">Loading projects...</div>
      ) : filteredProjects.length === 0 ? (
        <div className="empty-state">No projects found</div>
      ) : (
        <div className="wm-card" style={{ overflow: 'hidden' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Repository</th>
                <th>Branch</th>
                <th>Status</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {filteredProjects.map(project => (
                <tr key={project.id} onClick={() => onNavigate('project', project.id)}>
                  <td>
                    <span style={{ fontWeight: 500, color: 'var(--frost-500)' }}>{project.name}</span>
                    {project.description && (
                      <p style={{ margin: '0.25rem 0 0', fontSize: '0.75rem', color: 'rgb(var(--color-text-tertiary))' }}>{project.description}</p>
                    )}
                  </td>
                  <td style={{ fontSize: '0.875rem', color: 'rgb(var(--color-text-tertiary))' }}>{project.git_url || '—'}</td>
                  <td><span className="code-text">{project.base_branch}</span></td>
                  <td><StatusBadge status={project.status || 'active'} /></td>
                  <td style={{ fontSize: '0.875rem', color: 'rgb(var(--color-text-tertiary))' }}>{project.created_at?.slice(0, 10) || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// Project Detail Component
function ProjectDetail({ projectId, onNavigate }: { projectId: number; onNavigate: (view: string, id?: number) => void }) {
  const [project, setProject] = useState<Project | null>(null);
  const [protocols, setProtocols] = useState<Protocol[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [projectResult, protocolsResult] = await Promise.all([
        executeWorkspaceScript("u/devgodzilla/get_project", { project_id: projectId }),
        executeWorkspaceScript("u/devgodzilla/list_protocols", { project_id: projectId }),
      ]);
      if (projectResult?.project) {
        setProject(projectResult.project);
      } else {
        setError(projectResult?.error || "Project not found");
      }
      setProtocols(protocolsResult?.protocols || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load project");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  if (loading) return <div style={{ maxWidth: '80rem', margin: '0 auto', padding: '1.5rem 1rem' }}><div className="loading-state">Loading project...</div></div>;
  if (error || !project) return (
    <div style={{ maxWidth: '80rem', margin: '0 auto', padding: '1.5rem 1rem' }}>
      <button onClick={() => onNavigate('projects')} className="back-link">← Back to Projects</button>
      <div className="error-state">{error || "Project not found"}</div>
    </div>
  );

  return (
    <div style={{ maxWidth: '80rem', margin: '0 auto', padding: '1.5rem 1rem' }}>
      <button onClick={() => onNavigate('projects')} className="back-link">← Back to Projects</button>

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '2rem' }}>
        <div>
          <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            {project.name}
            <StatusBadge status={project.status || 'active'} />
          </h1>
          {project.description && <p className="page-subtitle">{project.description}</p>}
        </div>
        <div className="btn-group">
          <button className="wm-btn-primary" onClick={() => onNavigate('spec-editor', projectId)}>📝 Specifications</button>
          <button className="wm-btn-secondary" onClick={() => onNavigate('stories', projectId)}>📖 User Stories</button>
          <button className="wm-btn-secondary">✏️ Rename</button>
          <button className="wm-btn-secondary" style={project.status === 'archived' ? { background: '#dcfce7', borderColor: '#22c55e', color: '#166534' } : { background: '#fef3c7', borderColor: '#f59e0b', color: '#92400e' }}>
            {project.status === 'archived' ? '📦 Unarchive' : '📦 Archive'}
          </button>
        </div>
      </div>

      {/* Info Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '2rem' }}>
        <div className="stat-card">
          <p className="stat-label">Repository</p>
          <p style={{ fontSize: '0.875rem', fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis' }}>{project.git_url || '—'}</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Base Branch</p>
          <span className="code-text">{project.base_branch}</span>
        </div>
        <div className="stat-card">
          <p className="stat-label">Local Path</p>
          <p style={{ fontSize: '0.875rem', fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis' }}>{project.local_path || '—'}</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Constitution</p>
          <p style={{ fontSize: '0.875rem', fontWeight: 500 }}>{project.constitution_version || 'v1.0'}</p>
        </div>
      </div>

      {/* Protocols Section */}
      <div className="wm-card">
        <div style={{ padding: '1rem 1.5rem', borderBottom: '1px solid rgb(var(--color-surface-hover))', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600 }}>Protocols ({protocols.length})</h3>
          <button className="wm-btn-primary" style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}>➕ New Protocol</button>
        </div>
        <div>
          {protocols.length === 0 ? (
            <div className="empty-state">No protocols for this project yet</div>
          ) : (
            protocols.map(protocol => (
              <div key={protocol.id} onClick={() => onNavigate('protocol', protocol.id)} className="list-item-hover" style={{ padding: '0.75rem 1.5rem', cursor: 'pointer', borderBottom: '1px solid rgb(var(--color-surface-hover))' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <p style={{ margin: 0, fontWeight: 500 }}>{protocol.protocol_name}</p>
                    <p style={{ margin: '0.25rem 0 0', fontSize: '0.875rem', color: 'rgb(var(--color-text-tertiary))' }}>
                      {protocol.created_at ? new Date(protocol.created_at).toLocaleDateString() : '—'}
                    </p>
                  </div>
                  <StatusBadge status={protocol.status} />
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Timestamps */}
      <div style={{ marginTop: '1.5rem', fontSize: '0.875rem', color: 'rgb(var(--color-text-tertiary))', display: 'flex', gap: '1.5rem' }}>
        <span>Created: {project.created_at ? new Date(project.created_at).toLocaleString() : '—'}</span>
        <span>Updated: {project.updated_at ? new Date(project.updated_at).toLocaleString() : '—'}</span>
      </div>
    </div>
  );
}

// Protocols List Component
function ProtocolsList({ onNavigate }: { onNavigate: (view: string, id?: number) => void }) {
  const [protocols, setProtocols] = useState<Protocol[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");

  const loadProtocols = useCallback(async () => {
    setLoading(true);
    try {
      const result = await executeWorkspaceScript("u/devgodzilla/list_protocols", { status: statusFilter || undefined });
      setProtocols(result?.protocols || []);
    } catch (e) {
      console.error("Failed to load protocols:", e);
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    loadProtocols();
  }, [loadProtocols]);

  return (
    <div style={{ maxWidth: '80rem', margin: '0 auto', padding: '1.5rem 1rem' }}>
      <button onClick={() => onNavigate('dashboard')} className="back-link">← Back to Dashboard</button>
      <h1 className="page-title" style={{ marginBottom: '1.5rem' }}>Protocols</h1>

      {/* Filter */}
      <div style={{ marginBottom: '1.5rem' }}>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="form-input" style={{ width: 'auto' }}>
          <option value="">All Statuses</option>
          <option value="pending">Pending</option>
          <option value="running">Running</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
        </select>
      </div>

      {/* Table */}
      {loading ? (
        <div className="loading-state">Loading protocols...</div>
      ) : protocols.length === 0 ? (
        <div className="empty-state">No protocols found</div>
      ) : (
        <div className="wm-card" style={{ overflow: 'hidden' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Protocol</th>
                <th>Project</th>
                <th>Status</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {protocols.map(protocol => (
                <tr key={protocol.id} onClick={() => onNavigate('protocol', protocol.id)}>
                  <td><span style={{ fontWeight: 500, color: 'var(--frost-500)' }}>{protocol.protocol_name}</span></td>
                  <td style={{ fontSize: '0.875rem', color: 'rgb(var(--color-text-tertiary))' }}>Project #{protocol.project_id}</td>
                  <td><StatusBadge status={protocol.status} /></td>
                  <td style={{ fontSize: '0.875rem', color: 'rgb(var(--color-text-tertiary))' }}>{protocol.created_at?.slice(0, 10) || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// Protocol Detail Component - Enhanced with DAG Viewer and Tabs
function ProtocolDetail({ protocolId, onNavigate }: { protocolId: number; onNavigate: (view: string, id?: number) => void }) {
  const [protocol, setProtocol] = useState<Protocol | null>(null);
  const [steps, setSteps] = useState<Step[]>([]);
  const [stepCount, setStepCount] = useState(0);
  const [completedCount, setCompletedCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionBusy, setActionBusy] = useState<null | "plan" | "next" | `step:${number}`>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // New state for enhanced features
  const [activeTab, setActiveTab] = useState<string>("dag");
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null);
  const [showAgentSelector, setShowAgentSelector] = useState(false);
  const [agentSelectorStep, setAgentSelectorStep] = useState<Step | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await executeWorkspaceScript("u/devgodzilla/get_protocol", { protocol_id: protocolId });
      if (result?.protocol) {
        setProtocol(result.protocol);
        setSteps(result.steps || []);
        setStepCount(result.step_count || 0);
        setCompletedCount(result.completed_count || 0);
      } else {
        setError(result?.error || "Protocol not found");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load protocol");
    } finally {
      setLoading(false);
    }
  }, [protocolId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Convert steps to DAG format for TaskDAGViewer
  const dagTasks: Task[] = steps.map(step => ({
    id: `S${step.id}`,
    description: step.step_name,
    parallel: !!step.parallel_group,
    depends_on: (step.depends_on || []).map((dep) => `S${dep}`),
    status: step.status as StepStatus,
  }));

  const dagDefinition: DAGDefinition = {
    nodes: dagTasks.map(t => t.id),
    edges: dagTasks.flatMap(t => t.depends_on.map(dep => [dep, t.id] as [string, string])),
  };

  const handleTaskClick = (taskId: string) => {
    setSelectedStepId(taskId);
    // Find the corresponding step
    const stepId = parseInt(taskId.slice(1), 10);
    const step = steps.find(s => s.id === stepId);
    if (step) {
      console.log('Selected step:', step);
    }
  };

  const handleAssignAgent = (step: Step) => {
    setAgentSelectorStep(step);
    setShowAgentSelector(true);
  };

  const handleAgentAssigned = async (assignment: { agent_id: string; config_override?: object }) => {
    if (agentSelectorStep) {
      console.log(`Assigning agent ${assignment.agent_id} to step ${agentSelectorStep.id}`);
      // In a real implementation, call the API here
      // await api.steps.assignAgent(agentSelectorStep.id, assignment);
    }
    setShowAgentSelector(false);
    setAgentSelectorStep(null);
  };

  const statusIcons: Record<string, string> = { pending: "⏳", running: "🔄", completed: "✅", failed: "❌", blocked: "🚫" };

  const tabs = [
    { id: 'dag', label: 'Task Graph', icon: '📊' },
    { id: 'steps', label: 'Steps List', icon: '📋' },
    { id: 'feedback', label: 'Feedback', icon: '💬' },
  ];

  if (loading) return <div style={{ maxWidth: '80rem', margin: '0 auto', padding: '1.5rem 1rem' }}><div className="loading-state">Loading protocol...</div></div>;
  if (error || !protocol) return (
    <div style={{ maxWidth: '80rem', margin: '0 auto', padding: '1.5rem 1rem' }}>
      <button onClick={() => onNavigate('protocols')} className="back-link">← Back to Protocols</button>
      <div className="error-state">{error || "Protocol not found"}</div>
    </div>
  );

  const progressPercent = stepCount > 0 ? Math.round((completedCount / stepCount) * 100) : 0;
  const completedStepIds = new Set(steps.filter(s => s.status === "completed").map(s => s.id));

  const runPlan = async () => {
    setActionError(null);
    setActionBusy("plan");
    try {
      await executeWorkspaceScript("u/devgodzilla/protocol_plan_and_wait", { protocol_run_id: protocolId });
      await loadData();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "Failed to plan protocol");
    } finally {
      setActionBusy(null);
    }
  };

  const defaultQaGates = ["lint"];

  const runNextStep = async () => {
    setActionError(null);
    setActionBusy("next");
    try {
      const selected = await executeWorkspaceScript("u/devgodzilla/protocol_select_next_step", { protocol_run_id: protocolId });
      const stepRunId = selected?.step_run_id as number | null | undefined;
      if (!stepRunId) {
        setActionError("No runnable steps found");
        return;
      }
      await runStepWithQa(stepRunId);
      await loadData();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "Failed to run next step");
    } finally {
      setActionBusy(null);
    }
  };

  const runStepWithQa = async (stepRunId: number) => {
    setActionError(null);
    setActionBusy(`step:${stepRunId}`);
    try {
      await executeWorkspaceScript("u/devgodzilla/step_execute_api", { step_run_id: stepRunId });
      await executeWorkspaceScript("u/devgodzilla/step_run_qa_api", { step_run_id: stepRunId, gates: defaultQaGates });
      await loadData();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "Failed to execute step");
    } finally {
      setActionBusy(null);
    }
  };

  return (
    <div style={{ maxWidth: '80rem', margin: '0 auto', padding: '1.5rem 1rem' }}>
      <button onClick={() => onNavigate('protocols')} className="back-link">← Back to Protocols</button>

      {actionError && <div className="error-state" style={{ marginTop: "1rem" }}>{actionError}</div>}

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '2rem' }}>
        <div>
          <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            {protocol.protocol_name}
            <StatusBadge status={protocol.status} />
          </h1>
          <p className="page-subtitle">Project #{protocol.project_id}</p>
          {protocol.summary && <p style={{ color: 'rgb(var(--color-text-tertiary))', marginTop: '0.25rem' }}>{protocol.summary}</p>}
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          {(protocol.status === "pending" || protocol.status === "planning") && (
            <button
              onClick={runPlan}
              disabled={actionBusy !== null}
              className="wm-btn-primary"
              title="Generate steps for this protocol"
            >
              {actionBusy === "plan" ? "Planning..." : "🧭 Plan"}
            </button>
          )}
          {(protocol.status === "planned" || protocol.status === "running") && (
            <button
              onClick={runNextStep}
              disabled={actionBusy !== null}
              className="wm-btn-primary"
              title="Execute the next runnable step (with QA)"
            >
              {actionBusy === "next" ? "Running..." : "▶️ Run Next Step"}
            </button>
          )}
          <button onClick={() => onNavigate('quality', protocolId)} className="wm-btn-secondary">📊 Quality</button>
          <button onClick={() => onNavigate('project', protocol.project_id)} className="wm-btn-secondary">View Project →</button>
        </div>
      </div>

      {/* Progress Card */}
      <div className="stat-card" style={{ marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
          <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600 }}>Progress</h3>
          <span style={{ fontSize: '0.875rem', color: 'rgb(var(--color-text-tertiary))' }}>{completedCount} / {stepCount} steps</span>
        </div>
        <div className="progress-bar">
          <div className={`progress-fill ${protocol.status === 'failed' ? 'progress-fill-error' : protocol.status === 'completed' ? 'progress-fill-success' : 'progress-fill-info'}`} style={{ width: `${progressPercent}%` }} />
        </div>
        <p style={{ fontSize: '0.875rem', color: 'rgb(var(--color-text-tertiary))', marginTop: '0.5rem' }}>{progressPercent}% complete</p>
      </div>

      {/* Tabs Navigation */}
      <Tabs tabs={tabs} activeTab={activeTab} onTabChange={setActiveTab} />

      {/* Tab Content */}
      <div style={{ marginTop: '1rem' }}>
        {/* DAG View Tab */}
        {activeTab === 'dag' && (
          <div className="wm-card">
            <div style={{ padding: '1rem 1.5rem', borderBottom: '1px solid rgb(var(--color-surface-hover))' }}>
              <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600 }}>Task Dependency Graph</h3>
              <p style={{ margin: '0.25rem 0 0', fontSize: '0.875rem', color: 'rgb(var(--color-text-tertiary))' }}>
                Click on a task to view details. {selectedStepId && `Selected: ${selectedStepId}`}
              </p>
            </div>
            <div style={{ padding: '1rem' }}>
              {dagTasks.length === 0 ? (
                <div className="empty-state">No tasks defined yet</div>
              ) : (
                <TaskDAGViewer
                  tasks={dagTasks}
                  dag={dagDefinition}
                  onTaskClick={handleTaskClick}
                  selectedTaskId={selectedStepId || undefined}
                />
              )}
            </div>
          </div>
        )}

        {/* Steps List Tab */}
        {activeTab === 'steps' && (
          <div className="wm-card">
            <div style={{ padding: '1rem 1.5rem', borderBottom: '1px solid rgb(var(--color-surface-hover))' }}>
              <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600 }}>Steps ({steps.length})</h3>
            </div>
            <div>
              {steps.length === 0 ? (
                <div className="empty-state">No steps defined</div>
              ) : (
                steps.sort((a, b) => a.step_index - b.step_index).map(step => (
                  <div key={step.id} className="list-item-hover" style={{ padding: '0.75rem 1.5rem', borderBottom: '1px solid rgb(var(--color-surface-hover))' }}>
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: '1rem' }}>
                      <span className="step-icon" title={step.status}>{statusIcons[step.status] || statusIcons.pending}</span>
                      <div style={{ flex: 1 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                          <div>
                            <p style={{ margin: 0, fontWeight: 500 }}>{step.step_index + 1}. {step.step_name}</p>
                            <p style={{ margin: '0.25rem 0 0', fontSize: '0.875rem', color: 'rgb(var(--color-text-tertiary))' }}>
                              {step.step_type}
                              {step.assigned_agent && (
                                <span onClick={() => handleAssignAgent(step)} style={{ cursor: 'pointer' }}>
                                  {' • '}<AgentBadge agentId={step.assigned_agent} />
                                </span>
                              )}
                              {!step.assigned_agent && step.status === 'pending' && (
                                <button
                                  onClick={() => handleAssignAgent(step)}
                                  className="btn-ghost"
                                  style={{ marginLeft: '0.5rem', fontSize: '0.75rem' }}
                                >
                                  + Assign Agent
                                </button>
                              )}
                            </p>
                          </div>
                          <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                            {step.status === "pending" && (
                              <button
                                onClick={() => runStepWithQa(step.id)}
                                disabled={
                                  actionBusy !== null ||
                                  !((step.depends_on || []).every((dep) => completedStepIds.has(dep)))
                                }
                                className="wm-btn-secondary"
                                title={
                                  (step.depends_on || []).every((dep) => completedStepIds.has(dep))
                                    ? "Execute this step (with QA)"
                                    : "Dependencies not satisfied"
                                }
                              >
                                {actionBusy === `step:${step.id}` ? "Running..." : "Run"}
                              </button>
                            )}
                            <StatusBadge status={step.status} />
                          </div>
                        </div>
                        {step.summary && <p style={{ fontSize: '0.875rem', color: 'rgb(var(--color-text-secondary))', marginTop: '0.5rem' }}>{step.summary}</p>}
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {/* Feedback Tab */}
        {activeTab === 'feedback' && (
          <FeedbackPanel
            protocolId={protocolId}
            onClarificationAnswer={(id, answer) => {
              console.log(`Answered clarification ${id}: ${answer}`);
              // Reload data after answering
              loadData();
            }}
          />
        )}
      </div>

      {/* Footer Info */}
      <div style={{ marginTop: '1.5rem', fontSize: '0.875rem', color: 'rgb(var(--color-text-tertiary))', display: 'flex', gap: '1.5rem' }}>
        <span>Created: {protocol.created_at ? new Date(protocol.created_at).toLocaleString() : '—'}</span>
        {protocol.base_branch && <span>Branch: {protocol.base_branch}</span>}
      </div>

      {/* Agent Selector Modal */}
      {showAgentSelector && agentSelectorStep && (
        <Modal
          isOpen={showAgentSelector}
          onClose={() => setShowAgentSelector(false)}
          title="Assign Agent"
          size="lg"
        >
          <AgentSelector
            stepId={String(agentSelectorStep.id)}
            stepName={agentSelectorStep.step_name}
            currentAgentId={agentSelectorStep.assigned_agent}
            onAssign={handleAgentAssigned}
            onCancel={() => setShowAgentSelector(false)}
          />
        </Modal>
      )}
    </div>
  );
}

// Clarifications List Component
function ClarificationsList({ onNavigate }: { onNavigate: (view: string, id?: number) => void }) {
  const [clarifications, setClarifications] = useState<Clarification[]>([]);
  const [openCount, setOpenCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>("");

  const loadClarifications = useCallback(async () => {
    setLoading(true);
    try {
      const result = await executeWorkspaceScript("u/devgodzilla/list_clarifications", { status: statusFilter || undefined });
      setClarifications(result?.clarifications || []);
      setOpenCount(result?.open_count || 0);
    } catch (e) {
      console.error("Failed to load clarifications:", e);
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    loadClarifications();
  }, [loadClarifications]);

  return (
    <div style={{ maxWidth: '80rem', margin: '0 auto', padding: '1.5rem 1rem' }}>
      <button onClick={() => onNavigate('dashboard')} className="back-link">← Back to Dashboard</button>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <h1 className="page-title">Clarifications</h1>
        {openCount > 0 && <span className="wm-badge wm-badge-warning">{openCount} pending</span>}
      </div>

      <div style={{ marginBottom: '1.5rem' }}>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="form-input" style={{ width: 'auto' }}>
          <option value="">All</option>
          <option value="open">Open</option>
          <option value="answered">Answered</option>
        </select>
      </div>

      {loading ? (
        <div className="loading-state">Loading clarifications...</div>
      ) : clarifications.length === 0 ? (
        <div className="empty-state">No clarifications found</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {clarifications.map(clarification => (
            <div key={clarification.id} className="wm-card" style={{ padding: '1.5rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem' }}>
                <div>
                  <p style={{ margin: 0, fontSize: '1.125rem', fontWeight: 500 }}>{clarification.question}</p>
                  <p style={{ margin: '0.25rem 0 0', fontSize: '0.875rem', color: 'rgb(var(--color-text-tertiary))' }}>
                    Protocol #{clarification.protocol_run_id} • {clarification.created_at ? new Date(clarification.created_at).toLocaleDateString() : ''}
                  </p>
                </div>
                <StatusBadge status={clarification.status} />
              </div>

              {clarification.status === 'open' && clarification.options && clarification.options.length > 0 && (
                <div className="btn-group" style={{ marginTop: '1rem' }}>
                  {clarification.options.map((option, idx) => (
                    <button key={idx} className="wm-btn-primary" style={{ background: '#dbeafe', color: '#1e40af', border: '1px solid #93c5fd' }}>{option}</button>
                  ))}
                </div>
              )}

              {clarification.status === 'answered' && clarification.answer && (
                <div style={{ marginTop: '1rem', background: '#dcfce7', padding: '0.75rem 1rem', borderRadius: '0.5rem' }}>
                  <p style={{ margin: 0, fontSize: '0.875rem', color: '#166534' }}><strong>Answer:</strong> {clarification.answer}</p>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// Create Project Component
function CreateProject({ onNavigate }: { onNavigate: (view: string, id?: number) => void }) {
  const [name, setName] = useState("");
  const [gitUrl, setGitUrl] = useState("");
  const [baseBranch, setBaseBranch] = useState("main");
  const [description, setDescription] = useState("");
  const [creating, setCreating] = useState(false);

  const handleCreate = async () => {
    if (!name.trim()) return;
    setCreating(true);
    try {
      await executeWorkspaceScript("u/devgodzilla/create_project", {
        name: name.trim(),
        git_url: gitUrl.trim() || undefined,
        base_branch: baseBranch.trim(),
        description: description.trim() || undefined,
      });
      onNavigate('projects');
    } catch (e) {
      console.error("Failed to create project:", e);
      alert("Failed to create project: " + (e instanceof Error ? e.message : "Unknown error"));
    } finally {
      setCreating(false);
    }
  };

  return (
    <div style={{ maxWidth: '40rem', margin: '0 auto', padding: '1.5rem 1rem' }}>
      <button onClick={() => onNavigate('projects')} className="back-link">← Back to Projects</button>
      <h1 className="page-title" style={{ marginBottom: '2rem' }}>Create New Project</h1>

      <div className="wm-card" style={{ padding: '1.5rem' }}>
        <div className="form-group">
          <label className="form-label">Project Name *</label>
          <input type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="my-awesome-project" className="form-input" />
        </div>

        <div className="form-group">
          <label className="form-label">Git Repository URL</label>
          <input type="text" value={gitUrl} onChange={(e) => setGitUrl(e.target.value)} placeholder="https://github.com/username/repo" className="form-input" />
        </div>

        <div className="form-group">
          <label className="form-label">Base Branch</label>
          <input type="text" value={baseBranch} onChange={(e) => setBaseBranch(e.target.value)} placeholder="main" className="form-input" />
        </div>

        <div className="form-group">
          <label className="form-label">Description</label>
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Brief description..." rows={3} className="form-input" />
        </div>

        <div className="btn-group" style={{ paddingTop: '1rem' }}>
          <button onClick={handleCreate} disabled={!name.trim() || creating} className="wm-btn-primary">
            {creating ? "Creating..." : "Create Project"}
          </button>
          <button onClick={() => onNavigate('projects')} className="wm-btn-secondary">Cancel</button>
        </div>
      </div>
    </div>
  );
}

// Quality View Component - Wraps QADashboard for protocol quality display
function QualityView({ protocolId, onNavigate }: { protocolId: number; onNavigate: (view: string, id?: number) => void }) {
  return (
    <div style={{ maxWidth: '80rem', margin: '0 auto', padding: '1.5rem 1rem' }}>
      <button onClick={() => onNavigate('protocol', protocolId)} className="back-link">← Back to Protocol</button>
      <div className="page-header" style={{ marginBottom: '1.5rem' }}>
        <h1 className="page-title">Quality Assurance</h1>
        <p className="page-subtitle">Protocol #{protocolId}</p>
      </div>
      <QADashboard protocolId={protocolId} />
    </div>
  );
}

// Project Onboarding View - Multi-step project creation wizard
function OnboardingView({ onNavigate }: { onNavigate: (view: string, id?: number) => void }) {
  return (
    <div style={{ maxWidth: '80rem', margin: '0 auto', padding: '1.5rem 1rem' }}>
      <button onClick={() => onNavigate('projects')} className="back-link">← Back to Projects</button>
      <ProjectOnboarding
        onComplete={(projectId) => onNavigate('project', projectId)}
        onCancel={() => onNavigate('projects')}
      />
    </div>
  );
}

// Specification Editor View - For editing .specify/ files
function SpecEditorView({ projectId, onNavigate }: { projectId: number; onNavigate: (view: string, id?: number) => void }) {
  return (
    <div style={{ maxWidth: '80rem', margin: '0 auto', padding: '1.5rem 1rem' }}>
      <button onClick={() => onNavigate('project', projectId)} className="back-link">← Back to Project</button>
      <div className="page-header" style={{ marginBottom: '1.5rem' }}>
        <h1 className="page-title">Specification Editor</h1>
        <p className="page-subtitle">Project #{projectId}</p>
      </div>
      <SpecificationEditor
        projectId={projectId}
        filePath="constitution.md"
        onCancel={() => onNavigate('project', projectId)}
      />
    </div>
  );
}

// User Stories View - Project user story tracker
function StoriesView({ projectId, onNavigate }: { projectId: number; onNavigate: (view: string, id?: number) => void }) {
  return (
    <div style={{ maxWidth: '80rem', margin: '0 auto', padding: '1.5rem 1rem' }}>
      <button onClick={() => onNavigate('project', projectId)} className="back-link">← Back to Project</button>
      <UserStoryTracker projectId={projectId} />
    </div>
  );
}

// Jobs Monitor View - For viewing running and completed jobs
function JobsView({ protocolId, onNavigate }: { protocolId?: number; onNavigate: (view: string, id?: number) => void }) {
  return (
    <div style={{ maxWidth: '80rem', margin: '0 auto', padding: '1.5rem 1rem' }}>
      <button onClick={() => onNavigate(protocolId ? 'protocol' : 'dashboard', protocolId)} className="back-link">
        ← Back to {protocolId ? 'Protocol' : 'Dashboard'}
      </button>
      <div className="page-header" style={{ marginBottom: '1.5rem' }}>
        <h1 className="page-title">Jobs Monitor</h1>
        {protocolId && <p className="page-subtitle">Protocol #{protocolId}</p>}
      </div>
      <JobsMonitor protocolId={protocolId} showHistory={true} />
    </div>
  );
}

// Agent Configuration View - For managing AI agent configurations
function AgentConfigView({ onNavigate }: { onNavigate: (view: string, id?: number) => void }) {
  return (
    <div style={{ maxWidth: '80rem', margin: '0 auto', padding: '1.5rem 1rem' }}>
      <button onClick={() => onNavigate('dashboard')} className="back-link">← Back to Dashboard</button>
      <div className="page-header" style={{ marginBottom: '1.5rem' }}>
        <h1 className="page-title">Agent Configurations</h1>
        <p className="page-subtitle">Manage AI agent settings and capabilities</p>
      </div>
      <AgentConfigManager />
    </div>
  );
}

// Main App Component
function App() {
  const [view, setView] = useState<string>("dashboard");
  const [selectedId, setSelectedId] = useState<number | undefined>();

  const handleNavigate = useCallback((newView: string, id?: number) => {
    setView(newView);
    setSelectedId(id);
  }, []);

  return (
    <div className="app-wrapper">
      {view === "dashboard" && <Dashboard onNavigate={handleNavigate} />}
      {view === "projects" && <ProjectsList onNavigate={handleNavigate} />}
      {view === "project" && selectedId && <ProjectDetail projectId={selectedId} onNavigate={handleNavigate} />}
      {view === "protocols" && <ProtocolsList onNavigate={handleNavigate} />}
      {view === "protocol" && selectedId && <ProtocolDetail protocolId={selectedId} onNavigate={handleNavigate} />}
      {view === "clarifications" && <ClarificationsList onNavigate={handleNavigate} />}
      {view === "create-project" && <CreateProject onNavigate={handleNavigate} />}
      {view === "quality" && selectedId && <QualityView protocolId={selectedId} onNavigate={handleNavigate} />}
      {view === "onboarding" && <OnboardingView onNavigate={handleNavigate} />}
      {view === "spec-editor" && selectedId && <SpecEditorView projectId={selectedId} onNavigate={handleNavigate} />}
      {view === "stories" && selectedId && <StoriesView projectId={selectedId} onNavigate={handleNavigate} />}
      {view === "jobs" && <JobsView protocolId={selectedId} onNavigate={handleNavigate} />}
      {view === "agent-config" && <AgentConfigView onNavigate={handleNavigate} />}
    </div>
  );
}

export default App;
