<script lang="ts">
    import { createEventDispatcher, onMount } from 'svelte';
    
    // export let projectId: number = 0; // Unused
    
    const dispatch = createEventDispatcher();
    
    interface Agent {
        id: string;
        name: string;
        kind: 'cli' | 'ide' | 'api';
        enabled: boolean;
        model: string;
        sandbox: string;
        capabilities: string[];
        status: 'available' | 'unavailable' | 'checking';
    }
    
    let agents: Agent[] = [];
    let loading = true;
    // let selectedAgent: Agent | null = null; // Unused
    
    async function loadAgents() {
        loading = true;
        try {
            // Mock data - would fetch from /agents API
            agents = [
                {
                    id: 'codex',
                    name: 'OpenAI Codex',
                    kind: 'cli',
                    enabled: true,
                    model: 'gpt-4.1',
                    sandbox: 'workspace-write',
                    capabilities: ['code_gen', 'review', 'refactor'],
                    status: 'available'
                },
                {
                    id: 'opencode',
                    name: 'OpenCode',
                    kind: 'cli',
                    enabled: true,
                    model: 'claude-sonnet-4-20250514',
                    sandbox: 'workspace-write',
                    capabilities: ['code_gen', 'review', 'refactor'],
                    status: 'available'
                },
                {
                    id: 'claude-code',
                    name: 'Claude Code',
                    kind: 'cli',
                    enabled: true,
                    model: 'claude-sonnet-4-20250514',
                    sandbox: 'workspace-write',
                    capabilities: ['code_gen', 'review', 'refactor', 'long_context'],
                    status: 'available'
                },
                {
                    id: 'gemini-cli',
                    name: 'Gemini CLI',
                    kind: 'cli',
                    enabled: true,
                    model: 'gemini-2.5-pro',
                    sandbox: 'workspace-write',
                    capabilities: ['code_gen', 'review', 'multimodal'],
                    status: 'checking'
                },
                {
                    id: 'cursor',
                    name: 'Cursor Editor',
                    kind: 'ide',
                    enabled: false,
                    model: 'gpt-4',
                    sandbox: 'none',
                    capabilities: ['code_gen', 'interactive'],
                    status: 'unavailable'
                }
            ];
        } finally {
            loading = false;
        }
    }
    
    async function toggleAgent(agent: Agent) {
        agent.enabled = !agent.enabled;
        agents = agents;
        dispatch('change', { agentId: agent.id, enabled: agent.enabled });
    }
    
    async function checkHealth(agent: Agent) {
        agent.status = 'checking';
        agents = agents;
        
        // Simulate health check
        await new Promise(r => setTimeout(r, 1500));
        agent.status = Math.random() > 0.3 ? 'available' : 'unavailable';
        agents = agents;
    }
    
    function getStatusColor(status: string): string {
        switch (status) {
            case 'available': return '#22c55e';
            case 'unavailable': return '#ef4444';
            default: return '#eab308';
        }
    }
    
    function getKindIcon(kind: string): string {
        switch (kind) {
            case 'cli': return '⌨️';
            case 'ide': return '🖥️';
            case 'api': return '🌐';
            default: return '🤖';
        }
    }
    
    onMount(loadAgents);
</script>

<div class="manager">
    <div class="header">
        <h3>🤖 Agent Configuration</h3>
        <button class="btn-small" on:click={loadAgents}>↻ Refresh</button>
    </div>
    
    {#if loading}
        <div class="loading">Loading agents...</div>
    {:else}
        <div class="agents-list">
            {#each agents as agent}
                <div class="agent-row" class:disabled={!agent.enabled}>
                    <div class="agent-info">
                        <div class="agent-header">
                            <span class="kind-icon">{getKindIcon(agent.kind)}</span>
                            <span class="agent-name">{agent.name}</span>
                            <span class="status-dot" style="background: {getStatusColor(agent.status)}"></span>
                        </div>
                        <div class="agent-meta">
                            <span class="model">📦 {agent.model}</span>
                            <span class="sandbox">🔒 {agent.sandbox}</span>
                        </div>
                        <div class="capabilities">
                            {#each agent.capabilities as cap}
                                <span class="cap-tag">{cap}</span>
                            {/each}
                        </div>
                    </div>
                    
                    <div class="agent-actions">
                        <button 
                            class="btn-icon"
                            title="Check health"
                            on:click={() => checkHealth(agent)}
                            disabled={agent.status === 'checking'}
                        >
                            {agent.status === 'checking' ? '⏳' : '🔍'}
                        </button>
                        
                        <label class="toggle">
                            <input 
                                type="checkbox" 
                                checked={agent.enabled}
                                on:change={() => toggleAgent(agent)}
                            />
                            <span class="slider"></span>
                        </label>
                    </div>
                </div>
            {/each}
        </div>
        
        <div class="summary">
            <span>{agents.filter(a => a.enabled).length} / {agents.length} agents enabled</span>
        </div>
    {/if}
</div>

<style>
    .manager {
        font-family: system-ui, sans-serif;
        background: var(--bg-primary, #1a1a2e);
        border-radius: 8px;
        color: var(--text-primary, #e0e0e0);
        padding: 1rem;
    }
    
    .header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1rem;
    }
    
    h3 {
        margin: 0;
    }
    
    .btn-small {
        padding: 0.25rem 0.5rem;
        background: var(--bg-secondary, #2d2d44);
        border: none;
        border-radius: 4px;
        color: var(--text-secondary, #a0a0a0);
        cursor: pointer;
    }
    
    .agents-list {
        display: flex;
        flex-direction: column;
        gap: 0.75rem;
    }
    
    .agent-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 1rem;
        background: var(--bg-secondary, #2d2d44);
        border-radius: 8px;
        border-left: 3px solid var(--accent, #4f46e5);
    }
    
    .agent-row.disabled {
        opacity: 0.5;
        border-left-color: var(--text-secondary, #a0a0a0);
    }
    
    .agent-info {
        flex: 1;
    }
    
    .agent-header {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin-bottom: 0.25rem;
    }
    
    .agent-name {
        font-weight: 600;
    }
    
    .status-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
    }
    
    .agent-meta {
        display: flex;
        gap: 1rem;
        font-size: 0.8rem;
        color: var(--text-secondary, #a0a0a0);
        margin-bottom: 0.5rem;
    }
    
    .capabilities {
        display: flex;
        flex-wrap: wrap;
        gap: 0.25rem;
    }
    
    .cap-tag {
        padding: 0.125rem 0.375rem;
        background: rgba(79, 70, 229, 0.2);
        border-radius: 4px;
        font-size: 0.7rem;
        color: var(--accent, #4f46e5);
    }
    
    .agent-actions {
        display: flex;
        align-items: center;
        gap: 1rem;
    }
    
    .btn-icon {
        background: none;
        border: none;
        font-size: 1.25rem;
        cursor: pointer;
    }
    
    .btn-icon:disabled {
        opacity: 0.5;
        cursor: not-allowed;
    }
    
    .toggle {
        position: relative;
        width: 48px;
        height: 24px;
    }
    
    .toggle input {
        opacity: 0;
        width: 0;
        height: 0;
    }
    
    .slider {
        position: absolute;
        inset: 0;
        background: var(--bg-primary, #1a1a2e);
        border-radius: 24px;
        cursor: pointer;
        transition: 0.3s;
    }
    
    .slider:before {
        content: '';
        position: absolute;
        height: 18px;
        width: 18px;
        left: 3px;
        bottom: 3px;
        background: white;
        border-radius: 50%;
        transition: 0.3s;
    }
    
    input:checked + .slider {
        background: #22c55e;
    }
    
    input:checked + .slider:before {
        transform: translateX(24px);
    }
    
    .summary {
        margin-top: 1rem;
        text-align: center;
        font-size: 0.9rem;
        color: var(--text-secondary, #a0a0a0);
    }
    
    .loading {
        text-align: center;
        padding: 2rem;
        color: var(--text-secondary, #a0a0a0);
    }
</style>
