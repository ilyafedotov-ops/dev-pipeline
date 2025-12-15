/**
 * DevGodzilla API Client
 * 
 * Interacts with the DevGodzilla Python REST API.
 */

// API base URL - configurable for different environments
const API_BASE_URL = 'http://192.168.1.227';

export interface Project {
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

export interface ProtocolRun {
    id: number;
    project_id: number;
    protocol_name: string;
    status: string;
    base_branch?: string;
    worktree_path?: string;
    summary?: string;
    description?: string;
    created_at: string;
    updated_at?: string;
}

export interface StepRun {
    id: number;
    protocol_run_id: number;
    step_index: number;
    step_name: string;
    step_type: string;
    status: string;
    assigned_agent?: string;
    depends_on?: string[];
    parallel_group?: string;
    summary?: string;
}

export interface AgentInfo {
    id: string;
    name: string;
    kind: string;
    capabilities: string[];
    status?: string;
}

export interface Clarification {
    id: number;
    protocol_run_id?: number;
    question: string;
    status: 'open' | 'answered';
    answer?: Record<string, unknown>;
    options?: string[];
    created_at?: string;
    answered_at?: string;
}

export interface QAGate {
    id: string;
    name: string;
    status: 'passed' | 'warning' | 'failed' | 'skipped';
    findings: Array<{
        severity: string;
        message: string;
        file?: string;
        line?: number;
    }>;
}

export interface QAResult {
    verdict: 'passed' | 'warning' | 'failed';
    summary?: string;
    gates: QAGate[];
}

export interface SpecKitResponse {
    success: boolean;
    path?: string;
    constitution_hash?: string;
    error?: string;
    warnings?: string[];
}

export interface SpecifyResponse {
    success: boolean;
    spec_path?: string;
    spec_number?: number;
    feature_name?: string;
    error?: string;
}

export interface SpecListItem {
    name: string;
    path: string;
    has_spec: boolean;
    has_plan: boolean;
    has_tasks: boolean;
}

export interface SpecKitStatus {
    initialized: boolean;
    constitution_hash?: string;
    constitution_version?: string;
    spec_count: number;
    specs?: SpecListItem[];
}

export class DevGodzillaClient {
    private baseUrl: string;

    constructor(baseUrl: string = API_BASE_URL) {
        this.baseUrl = baseUrl;
    }

    private async request<T>(path: string, options?: RequestInit): Promise<T> {
        const url = `${this.baseUrl}${path}`;
        const response = await fetch(url, options);

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`API Error ${response.status}: ${errorText}`);
        }

        return response.json();
    }

    // Health check
    async health(): Promise<{ status: string; version: string }> {
        return this.request('/health');
    }

    // =========================================================================
    // Projects
    // =========================================================================

    async listProjects(): Promise<Project[]> {
        return this.request<Project[]>("/projects");
    }

    async createProject(data: Partial<Project>): Promise<Project> {
        return this.request<Project>("/projects", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data),
        });
    }

    async getProject(id: number): Promise<Project> {
        return this.request<Project>(`/projects/${id}`);
    }

    async updateProject(id: number, data: Partial<Project>): Promise<Project> {
        return this.request<Project>(`/projects/${id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data),
        });
    }

    // =========================================================================
    // Protocols
    // =========================================================================

    async listProtocols(projectId?: number, status?: string): Promise<ProtocolRun[]> {
        const params = new URLSearchParams();
        if (projectId) params.append('project_id', String(projectId));
        if (status) params.append('status', status);
        const query = params.toString();
        return this.request<ProtocolRun[]>(`/protocols${query ? '?' + query : ''}`);
    }

    async createProtocol(data: {
        project_id: number;
        name: string;
        description?: string;
        branch_name?: string
    }): Promise<ProtocolRun> {
        return this.request<ProtocolRun>("/protocols", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data),
        });
    }

    async getProtocol(id: number): Promise<ProtocolRun> {
        return this.request<ProtocolRun>(`/protocols/${id}`);
    }

    async startProtocol(id: number): Promise<ProtocolRun> {
        return this.request<ProtocolRun>(`/protocols/${id}/actions/start`, {
            method: "POST"
        });
    }

    async pauseProtocol(id: number): Promise<ProtocolRun> {
        return this.request<ProtocolRun>(`/protocols/${id}/actions/pause`, {
            method: "POST"
        });
    }

    async resumeProtocol(id: number): Promise<ProtocolRun> {
        return this.request<ProtocolRun>(`/protocols/${id}/actions/resume`, {
            method: "POST"
        });
    }

    async cancelProtocol(id: number): Promise<ProtocolRun> {
        return this.request<ProtocolRun>(`/protocols/${id}/actions/cancel`, {
            method: "POST"
        });
    }

    // =========================================================================
    // Steps
    // =========================================================================

    async listSteps(protocolId: number, status?: string): Promise<StepRun[]> {
        const params = new URLSearchParams();
        params.append('protocol_run_id', String(protocolId));
        if (status) params.append('status', status);
        return this.request<StepRun[]>(`/steps?${params.toString()}`);
    }

    async getStep(id: number): Promise<StepRun> {
        return this.request<StepRun>(`/steps/${id}`);
    }

    async executeStep(id: number): Promise<StepRun> {
        return this.request<StepRun>(`/steps/${id}/actions/execute`, {
            method: "POST"
        });
    }

    async runStepQA(id: number, gates?: string[]): Promise<QAResult> {
        return this.request<QAResult>(`/steps/${id}/actions/qa`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ gates })
        });
    }

    // =========================================================================
    // Agents
    // =========================================================================

    async listAgents(): Promise<AgentInfo[]> {
        return this.request<AgentInfo[]>("/agents");
    }

    async getAgent(id: string): Promise<AgentInfo> {
        return this.request<AgentInfo>(`/agents/${id}`);
    }

    async checkAgentHealth(id: string): Promise<{ status: string }> {
        return this.request<{ status: string }>(`/agents/${id}/health`, {
            method: "POST"
        });
    }

    // =========================================================================
    // Clarifications
    // =========================================================================

    async listClarifications(
        projectId?: number,
        protocolId?: number,
        status?: 'open' | 'answered'
    ): Promise<Clarification[]> {
        const params = new URLSearchParams();
        if (projectId) params.append('project_id', String(projectId));
        if (protocolId) params.append('protocol_run_id', String(protocolId));
        if (status) params.append('status', status);
        const query = params.toString();
        return this.request<Clarification[]>(`/clarifications${query ? '?' + query : ''}`);
    }

    async answerClarification(id: number, answer: string): Promise<Clarification> {
        return this.request<Clarification>(`/clarifications/${id}/answer`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ answer })
        });
    }

    // =========================================================================
    // SpecKit
    // =========================================================================

    async initSpecKit(projectId: number, constitutionContent?: string): Promise<SpecKitResponse> {
        return this.request<SpecKitResponse>(`/speckit/init`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                project_id: projectId,
                constitution_content: constitutionContent
            })
        });
    }

    async getConstitution(projectId: number): Promise<{ content: string }> {
        return this.request<{ content: string }>(`/speckit/constitution/${projectId}`);
    }

    async updateConstitution(projectId: number, content: string): Promise<SpecKitResponse> {
        return this.request<SpecKitResponse>(`/speckit/constitution/${projectId}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ content })
        });
    }

    async runSpecify(
        projectId: number,
        description: string,
        featureName?: string
    ): Promise<SpecifyResponse> {
        return this.request<SpecifyResponse>(`/speckit/specify`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                project_id: projectId,
                description,
                feature_name: featureName
            })
        });
    }

    async runPlan(projectId: number, specPath: string): Promise<{
        success: boolean;
        plan_path?: string;
        data_model_path?: string;
        contracts_path?: string;
        error?: string;
    }> {
        return this.request(`/speckit/plan`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ project_id: projectId, spec_path: specPath })
        });
    }

    async runTasks(projectId: number, planPath: string): Promise<{
        success: boolean;
        tasks_path?: string;
        task_count: number;
        parallelizable_count: number;
        error?: string;
    }> {
        return this.request(`/speckit/tasks`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ project_id: projectId, plan_path: planPath })
        });
    }

    async listSpecs(projectId: number): Promise<SpecListItem[]> {
        return this.request<SpecListItem[]>(`/speckit/specs/${projectId}`);
    }

    async getSpecKitStatus(projectId: number): Promise<SpecKitStatus> {
        return this.request<SpecKitStatus>(`/speckit/status/${projectId}`);
    }
}

// Default client instance pointing to the DevGodzilla backend
export const devGodzilla = new DevGodzillaClient();
