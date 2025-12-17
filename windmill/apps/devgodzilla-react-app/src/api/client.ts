// DevGodzilla API Client
// Typed client for all API endpoints

import { OpenAPI } from "windmill-client";
import { executeWorkspaceScript } from "../utils";
import type {
    Project,
    Protocol,
    Step,
    Clarification,
    Agent,
    AgentConfig,
    AgentAssignRequest,
    QualitySummary,
    FeedbackRequest,
    FeedbackResponse,
    FeedbackEvent,
    SpecifyRequest,
    SpecifyResponse,
    TasksResponse,
    HealthStatus,
    DashboardStats,
} from "../types";

// ============ Configuration ============

// When running as a Windmill app behind the same origin (nginx), prefer relative URLs.
// In local development, set `VITE_API_URL` to e.g. `http://localhost` (nginx) or `http://localhost:8000` (direct API).
const API_BASE_URL = import.meta.env.VITE_API_URL ?? "";

interface RequestOptions {
    method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
    body?: unknown;
    headers?: Record<string, string>;
}

// ============ Base Fetch Helper ============

async function apiFetch<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
    const { method = "GET", body, headers = {} } = options;

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        method,
        headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${OpenAPI.TOKEN}`,
            ...headers,
        },
        body: body ? JSON.stringify(body) : undefined,
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ message: response.statusText }));
        throw new Error(error.message || `API Error: ${response.status}`);
    }

    return response.json();
}

// ============ Windmill Script Helper ============

async function executeScript<T>(scriptPath: string, args: Record<string, unknown> = {}): Promise<T> {
    return executeWorkspaceScript(scriptPath, args) as Promise<T>;
}

// ============ Projects API ============

export const projectsApi = {
    list: async (): Promise<{ projects: Project[] }> => {
        return executeScript("u/devgodzilla/list_projects", {});
    },

    get: async (projectId: number): Promise<{ project: Project; error?: string }> => {
        return executeScript("u/devgodzilla/get_project", { project_id: projectId });
    },

    create: async (data: {
        name: string;
        git_url?: string;
        base_branch?: string;
        description?: string;
        project_classification?: string;
    }): Promise<{ project: Project }> => {
        return executeScript("u/devgodzilla/create_project", data);
    },

    update: async (projectId: number, data: Partial<Project>): Promise<{ project: Project }> => {
        return executeScript("u/devgodzilla/update_project", { project_id: projectId, ...data });
    },

    archive: async (projectId: number): Promise<void> => {
        await executeScript("u/devgodzilla/archive_project", { project_id: projectId });
    },

    unarchive: async (projectId: number): Promise<void> => {
        await executeScript("u/devgodzilla/unarchive_project", { project_id: projectId });
    },

    rename: async (projectId: number, newName: string): Promise<{ project: Project }> => {
        return executeScript("u/devgodzilla/rename_project", { project_id: projectId, name: newName });
    },
};

// ============ Protocols API ============

export const protocolsApi = {
    list: async (params?: { project_id?: number; status?: string }): Promise<{
        protocols: Protocol[];
        stats: { total: number; running: number; completed_today: number };
    }> => {
        return executeScript("u/devgodzilla/list_protocols", params || {});
    },

    get: async (protocolId: number): Promise<{
        protocol: Protocol;
        steps: Step[];
        step_count: number;
        completed_count: number;
        error?: string;
    }> => {
        return executeScript("u/devgodzilla/get_protocol", { protocol_id: protocolId });
    },

    create: async (data: {
        project_id: number;
        protocol_name: string;
        tasks_path?: string;
    }): Promise<{ protocol: Protocol }> => {
        return executeScript("u/devgodzilla/create_protocol", data);
    },

    // Protocol Actions
    start: async (protocolId: number): Promise<void> => {
        await apiFetch(`/protocols/${protocolId}/actions/start`, { method: "POST" });
    },

    pause: async (protocolId: number): Promise<void> => {
        await apiFetch(`/protocols/${protocolId}/actions/pause`, { method: "POST" });
    },

    resume: async (protocolId: number): Promise<void> => {
        await apiFetch(`/protocols/${protocolId}/actions/resume`, { method: "POST" });
    },

    cancel: async (protocolId: number): Promise<void> => {
        await apiFetch(`/protocols/${protocolId}/actions/cancel`, { method: "POST" });
    },

    runNextStep: async (protocolId: number): Promise<void> => {
        await apiFetch(`/protocols/${protocolId}/actions/run_next_step`, { method: "POST" });
    },

    retryLatest: async (protocolId: number): Promise<void> => {
        await apiFetch(`/protocols/${protocolId}/actions/retry_latest`, { method: "POST" });
    },
};

// ============ Steps API ============

export const stepsApi = {
    get: async (stepId: number): Promise<Step> => {
        return apiFetch(`/steps/${stepId}`);
    },

    run: async (stepId: number): Promise<void> => {
        await apiFetch(`/steps/${stepId}/actions/execute`, { method: "POST" });
    },

    runQA: async (stepId: number): Promise<void> => {
        await apiFetch(`/steps/${stepId}/actions/qa`, { method: "POST", body: {} });
    },

    approve: async (stepId: number): Promise<void> => {
        await apiFetch(`/steps/${stepId}/actions/approve`, { method: "POST" });
    },

    assignAgent: async (stepId: number, assignment: AgentAssignRequest): Promise<void> => {
        await apiFetch(`/steps/${stepId}/actions/assign_agent`, {
            method: "POST",
            body: assignment
        });
    },
};

// ============ Clarifications API ============

export const clarificationsApi = {
    list: async (params?: { protocol_id?: number; status?: string }): Promise<{
        clarifications: Clarification[];
        open_count: number;
    }> => {
        return executeScript("u/devgodzilla/list_clarifications", params || {});
    },

    answer: async (clarificationId: number, answer: string): Promise<void> => {
        await apiFetch(`/clarifications/${clarificationId}/answer`, {
            method: "POST",
            body: { answer },
        });
    },
};

// ============ Agents API ============

export const agentsApi = {
    list: async (): Promise<{ agents: Agent[] }> => {
        return apiFetch("/agents");
    },

    get: async (agentId: string): Promise<Agent> => {
        return apiFetch(`/agents/${agentId}`);
    },

    getConfig: async (agentId: string): Promise<AgentConfig> => {
        return apiFetch(`/agents/${agentId}/config`);
    },

    updateConfig: async (agentId: string, config: Partial<AgentConfig>): Promise<AgentConfig> => {
        return apiFetch(`/agents/${agentId}/config`, { method: "PUT", body: config });
    },

    checkHealth: async (agentId: string): Promise<{ status: string }> => {
        return apiFetch(`/agents/${agentId}/health`);
    },
};

// ============ SpecKit API ============

export const speckitApi = {
    init: async (projectId: number): Promise<{ success: boolean }> => {
        return apiFetch(`/projects/${projectId}/speckit/init`, { method: "POST" });
    },

    specify: async (projectId: number, data: SpecifyRequest): Promise<SpecifyResponse> => {
        return apiFetch(`/projects/${projectId}/speckit/specify`, { method: "POST", body: data });
    },

    plan: async (projectId: number, specId: string): Promise<{ plan_id: string; plan_path: string }> => {
        return apiFetch(`/projects/${projectId}/speckit/plan`, {
            method: "POST",
            body: { spec_id: specId }
        });
    },

    tasks: async (projectId: number, specId: string, planId: string): Promise<TasksResponse> => {
        return apiFetch(`/projects/${projectId}/speckit/tasks`, {
            method: "POST",
            body: { spec_id: specId, plan_id: planId }
        });
    },

    getConstitution: async (projectId: number): Promise<{ content: string; version: string }> => {
        return apiFetch(`/projects/${projectId}/speckit/constitution`);
    },

    updateConstitution: async (projectId: number, content: string): Promise<{ version: string }> => {
        return apiFetch(`/projects/${projectId}/speckit/constitution`, {
            method: "PUT",
            body: { content }
        });
    },
};

// ============ Quality API ============

export const qualityApi = {
    getSummary: async (protocolId: number): Promise<QualitySummary> => {
        return apiFetch(`/protocols/${protocolId}/quality`);
    },

    getGates: async (protocolId: number): Promise<{ gates: QualitySummary["gates"] }> => {
        return apiFetch(`/protocols/${protocolId}/quality/gates`);
    },

    getStepQuality: async (stepId: number): Promise<QualitySummary> => {
        return apiFetch(`/steps/${stepId}/quality`);
    },
};

// ============ Feedback API ============

export const feedbackApi = {
    list: async (protocolId: number): Promise<{ events: FeedbackEvent[] }> => {
        return apiFetch(`/protocols/${protocolId}/feedback`);
    },

    submit: async (protocolId: number, feedback: FeedbackRequest): Promise<FeedbackResponse> => {
        return apiFetch(`/protocols/${protocolId}/feedback`, { method: "POST", body: feedback });
    },
};

// ============ System API ============

export const systemApi = {
    health: async (): Promise<HealthStatus> => {
        return apiFetch("/health");
    },

    ready: async (): Promise<{ status: string }> => {
        return apiFetch("/health/ready");
    },
};

// ============ Dashboard Stats ============

export const dashboardApi = {
    getStats: async (): Promise<DashboardStats> => {
        const [projectsResult, protocolsResult, clarificationsResult] = await Promise.all([
            projectsApi.list(),
            protocolsApi.list(),
            clarificationsApi.list(),
        ]);

        const projects = projectsResult.projects || [];
        const stats = protocolsResult.stats || { total: 0, running: 0, completed_today: 0 };

        return {
            total_projects: projects.length,
            active_projects: projects.filter(p => p.status !== 'archived').length,
            archived_projects: projects.filter(p => p.status === 'archived').length,
            total_protocols: stats.total,
            running_protocols: stats.running,
            completed_today: stats.completed_today,
            pending_clarifications: clarificationsResult.open_count || 0,
        };
    },
};

// ============ SSE Event Stream ============

export function createEventStream(
    onEvent: (event: { type: string; data: unknown }) => void,
    onError?: (error: Error) => void
): () => void {
    const eventSource = new EventSource(`${API_BASE_URL}/events`);

    eventSource.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            onEvent({ type: event.type || 'message', data });
        } catch (e) {
            console.error('Failed to parse SSE event:', e);
        }
    };

    eventSource.onerror = (error) => {
        console.error('SSE connection error:', error);
        onError?.(new Error('SSE connection failed'));
    };

    // Return cleanup function
    return () => {
        eventSource.close();
    };
}

// ============ Combined API Export ============

export const api = {
    projects: projectsApi,
    protocols: protocolsApi,
    steps: stepsApi,
    clarifications: clarificationsApi,
    agents: agentsApi,
    speckit: speckitApi,
    quality: qualityApi,
    feedback: feedbackApi,
    system: systemApi,
    dashboard: dashboardApi,
    createEventStream,
};

export default api;
