<script lang="ts">
    import { createEventDispatcher } from 'svelte';
    import { devGodzilla as client } from './client';
    
    export let onComplete: (projectId: number) => void = () => {};
    
    const dispatch = createEventDispatcher();
    
    let currentStep = 1;
    const totalSteps = 4;
    
    // Form data
    let projectName = '';
    let repoUrl = '';
    let baseBranch = 'main';
    let projectType: 'python' | 'nodejs' | 'mixed' = 'python';
    let constitutionContent = '';
    let selectedAgents: string[] = ['opencode', 'claude-code'];
    
    const availableAgents = [
        { id: 'codex', name: 'OpenAI Codex', icon: '🤖' },
        { id: 'opencode', name: 'OpenCode', icon: '💻' },
        { id: 'claude-code', name: 'Claude Code', icon: '🧠' },
        { id: 'gemini-cli', name: 'Gemini CLI', icon: '✨' },
    ];
    
    const defaultConstitution = `# Project Constitution

## Core Values
1. **Safety First**: All generated code must be verified in sandboxes
2. **Library First**: Prefer established libraries over custom implementations
3. **Test Driven**: Write tests before implementation where possible

## Quality Gates
- All code must pass linting (ruff/eslint)
- All code must pass type checking (mypy/tsc)
- Tests must pass before merge
- Security scans must pass

## Constraints
- Follow existing code conventions
- Document public APIs
- Use dependency injection for testability
`;
    
    let isSubmitting = false;
    let error = '';
    
    function nextStep() {
        if (currentStep < totalSteps) {
            currentStep++;
        }
    }
    
    function prevStep() {
        if (currentStep > 1) {
            currentStep--;
        }
    }
    
    function toggleAgent(agentId: string) {
        if (selectedAgents.includes(agentId)) {
            selectedAgents = selectedAgents.filter(a => a !== agentId);
        } else {
            selectedAgents = [...selectedAgents, agentId];
        }
    }
    
    async function handleSubmit() {
        isSubmitting = true;
        error = '';
        
        try {
            // Create project
            const project = await client.createProject({
                name: projectName,
                git_url: repoUrl,
                base_branch: baseBranch,
            });
            
            // Initialize SpecKit
            await client.initSpecKit(project.id, constitutionContent || defaultConstitution);
            
            dispatch('complete', { projectId: project.id });
            onComplete(project.id);
        } catch (e) {
            error = e instanceof Error ? e.message : 'Failed to create project';
        } finally {
            isSubmitting = false;
        }
    }
    
    $: canProceed = currentStep === 1 ? projectName && repoUrl :
                    currentStep === 2 ? true :
                    currentStep === 3 ? selectedAgents.length > 0 :
                    true;
</script>

<div class="wizard">
    <div class="wizard-header">
        <h2>🚀 New Project Setup</h2>
        <div class="steps">
            {#each Array(totalSteps) as _, i}
                <div class="step" class:active={i + 1 === currentStep} class:completed={i + 1 < currentStep}>
                    {i + 1}
                </div>
                {#if i < totalSteps - 1}
                    <div class="step-line" class:completed={i + 1 < currentStep}></div>
                {/if}
            {/each}
        </div>
    </div>
    
    <div class="wizard-content">
        {#if currentStep === 1}
            <div class="step-content">
                <h3>Project Details</h3>
                <div class="form-group">
                    <label for="name">Project Name</label>
                    <input id="name" type="text" bind:value={projectName} placeholder="my-awesome-project" />
                </div>
                <div class="form-group">
                    <label for="repo">Repository URL</label>
                    <input id="repo" type="text" bind:value={repoUrl} placeholder="https://github.com/user/repo.git" />
                </div>
                <div class="form-group">
                    <label for="branch">Base Branch</label>
                    <input id="branch" type="text" bind:value={baseBranch} placeholder="main" />
                </div>
                <div class="form-group">
                    <label for="type">Project Type</label>
                    <select id="type" bind:value={projectType}>
                        <option value="python">Python</option>
                        <option value="nodejs">Node.js</option>
                        <option value="mixed">Mixed</option>
                    </select>
                </div>
            </div>
        {:else if currentStep === 2}
            <div class="step-content">
                <h3>Project Constitution</h3>
                <p class="hint">Define the rules and constraints for AI agents working on this project.</p>
                <textarea 
                    bind:value={constitutionContent}
                    placeholder={defaultConstitution}
                    rows="15"
                ></textarea>
            </div>
        {:else if currentStep === 3}
            <div class="step-content">
                <h3>Select AI Agents</h3>
                <p class="hint">Choose which AI agents can work on this project.</p>
                <div class="agents-grid">
                    {#each availableAgents as agent}
                        <button 
                            class="agent-card"
                            class:selected={selectedAgents.includes(agent.id)}
                            on:click={() => toggleAgent(agent.id)}
                        >
                            <span class="agent-icon">{agent.icon}</span>
                            <span class="agent-name">{agent.name}</span>
                        </button>
                    {/each}
                </div>
            </div>
        {:else if currentStep === 4}
            <div class="step-content">
                <h3>Review & Create</h3>
                <div class="review">
                    <div class="review-item">
                        <strong>Project:</strong> {projectName}
                    </div>
                    <div class="review-item">
                        <strong>Repository:</strong> {repoUrl}
                    </div>
                    <div class="review-item">
                        <strong>Branch:</strong> {baseBranch}
                    </div>
                    <div class="review-item">
                        <strong>Type:</strong> {projectType}
                    </div>
                    <div class="review-item">
                        <strong>Agents:</strong> {selectedAgents.join(', ')}
                    </div>
                </div>
                
                {#if error}
                    <div class="error">{error}</div>
                {/if}
            </div>
        {/if}
    </div>
    
    <div class="wizard-footer">
        {#if currentStep > 1}
            <button class="btn secondary" on:click={prevStep} disabled={isSubmitting}>
                ← Back
            </button>
        {:else}
            <div></div>
        {/if}
        
        {#if currentStep < totalSteps}
            <button class="btn primary" on:click={nextStep} disabled={!canProceed}>
                Next →
            </button>
        {:else}
            <button class="btn primary" on:click={handleSubmit} disabled={isSubmitting || !canProceed}>
                {isSubmitting ? 'Creating...' : 'Create Project 🎉'}
            </button>
        {/if}
    </div>
</div>

<style>
    .wizard {
        font-family: system-ui, sans-serif;
        max-width: 600px;
        margin: 0 auto;
        background: var(--bg-primary, #1a1a2e);
        border-radius: 12px;
        color: var(--text-primary, #e0e0e0);
        overflow: hidden;
    }
    
    .wizard-header {
        padding: 1.5rem;
        background: linear-gradient(135deg, #4f46e5, #7c3aed);
    }
    
    h2 {
        margin: 0 0 1rem;
        text-align: center;
    }
    
    .steps {
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 0;
    }
    
    .step {
        width: 32px;
        height: 32px;
        border-radius: 50%;
        background: rgba(255,255,255,0.2);
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 600;
        transition: all 0.3s;
    }
    
    .step.active {
        background: white;
        color: #4f46e5;
    }
    
    .step.completed {
        background: #22c55e;
    }
    
    .step-line {
        width: 40px;
        height: 2px;
        background: rgba(255,255,255,0.2);
    }
    
    .step-line.completed {
        background: #22c55e;
    }
    
    .wizard-content {
        padding: 1.5rem;
        min-height: 350px;
    }
    
    .step-content h3 {
        margin: 0 0 1rem;
    }
    
    .hint {
        color: var(--text-secondary, #a0a0a0);
        font-size: 0.9rem;
        margin-bottom: 1rem;
    }
    
    .form-group {
        margin-bottom: 1rem;
    }
    
    label {
        display: block;
        font-size: 0.9rem;
        margin-bottom: 0.25rem;
        color: var(--text-secondary, #a0a0a0);
    }
    
    input, select, textarea {
        width: 100%;
        padding: 0.75rem;
        background: var(--bg-secondary, #2d2d44);
        border: 1px solid var(--border, #3d3d5c);
        border-radius: 6px;
        color: var(--text-primary, #e0e0e0);
        font-size: 1rem;
    }
    
    input:focus, select:focus, textarea:focus {
        outline: none;
        border-color: var(--accent, #4f46e5);
    }
    
    textarea {
        font-family: monospace;
        resize: vertical;
    }
    
    .agents-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 1rem;
    }
    
    .agent-card {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 0.5rem;
        padding: 1rem;
        background: var(--bg-secondary, #2d2d44);
        border: 2px solid transparent;
        border-radius: 8px;
        cursor: pointer;
        transition: all 0.2s;
    }
    
    .agent-card:hover {
        border-color: var(--accent, #4f46e5);
    }
    
    .agent-card.selected {
        border-color: #22c55e;
        background: rgba(34, 197, 94, 0.1);
    }
    
    .agent-icon {
        font-size: 2rem;
    }
    
    .review {
        background: var(--bg-secondary, #2d2d44);
        border-radius: 8px;
        padding: 1rem;
    }
    
    .review-item {
        padding: 0.5rem 0;
        border-bottom: 1px solid var(--border, #3d3d5c);
    }
    
    .review-item:last-child {
        border-bottom: none;
    }
    
    .error {
        margin-top: 1rem;
        padding: 0.75rem;
        background: rgba(239, 68, 68, 0.2);
        border: 1px solid #ef4444;
        border-radius: 6px;
        color: #ef4444;
    }
    
    .wizard-footer {
        display: flex;
        justify-content: space-between;
        padding: 1rem 1.5rem;
        background: var(--bg-secondary, #2d2d44);
    }
    
    .btn {
        padding: 0.75rem 1.5rem;
        border: none;
        border-radius: 6px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s;
    }
    
    .btn.primary {
        background: linear-gradient(135deg, #4f46e5, #7c3aed);
        color: white;
    }
    
    .btn.primary:hover:not(:disabled) {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(79, 70, 229, 0.4);
    }
    
    .btn.secondary {
        background: transparent;
        color: var(--text-primary, #e0e0e0);
    }
    
    .btn:disabled {
        opacity: 0.5;
        cursor: not-allowed;
    }
</style>
