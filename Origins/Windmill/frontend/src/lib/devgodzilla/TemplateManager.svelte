<script lang="ts">
    import { createEventDispatcher } from 'svelte';
    
    // export let projectId: number = 0; // Unused
    
    const dispatch = createEventDispatcher();
    
    interface Template {
        id: string;
        name: string;
        type: 'spec' | 'plan' | 'tasks' | 'checklist';
        description: string;
        content: string;
        isDefault: boolean;
        lastModified: string;
    }
    
    let templates: Template[] = [];
    let selectedTemplate: Template | null = null;
    let editing = false;
    let editContent = '';
    let loading = true;
    
    const defaultTemplates: Template[] = [
        {
            id: 'spec-default',
            name: 'Feature Spec Template',
            type: 'spec',
            description: 'Default template for feature specifications',
            content: `# Feature: {{feature_name}}

## Overview
{{description}}

## User Stories
- As a {{user_type}}, I want to {{action}} so that {{benefit}}

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2

## Technical Notes
{{technical_notes}}`,
            isDefault: true,
            lastModified: '2024-01-01T00:00:00Z'
        },
        {
            id: 'plan-default',
            name: 'Implementation Plan Template',
            type: 'plan',
            description: 'Default template for implementation plans',
            content: `# Implementation Plan: {{feature_name}}

## Approach
{{approach}}

## Components
1. {{component_1}}
2. {{component_2}}

## Dependencies
- {{dependency_1}}

## Risks
- {{risk_1}}

## Timeline
- Phase 1: {{phase_1}}`,
            isDefault: true,
            lastModified: '2024-01-01T00:00:00Z'
        },
        {
            id: 'tasks-default',
            name: 'Task List Template',
            type: 'tasks',
            description: 'Default template for task breakdowns',
            content: `# Tasks: {{feature_name}}

## Setup
- [ ] Task 1 [P1] @agent:opencode
- [ ] Task 2 [P1] @agent:claude-code

## Implementation
- [ ] Task 3 [P2] depends:task1
- [ ] Task 4 [P2] depends:task2

## Testing
- [ ] Write unit tests [P1]
- [ ] Write integration tests [P2]

## Documentation
- [ ] Update README [P3]`,
            isDefault: true,
            lastModified: '2024-01-01T00:00:00Z'
        },
        {
            id: 'checklist-default',
            name: 'QA Checklist Template',
            type: 'checklist',
            description: 'Default template for quality checklists',
            content: `# QA Checklist: {{feature_name}}

## Required
- [ ] All tests pass
- [ ] No lint errors
- [ ] Type checking passes
- [ ] Documentation updated

## Recommended
- [ ] Security scan passes
- [ ] Code reviewed

## Optional
- [ ] Performance tested
- [ ] Accessibility checked`,
            isDefault: true,
            lastModified: '2024-01-01T00:00:00Z'
        }
    ];
    
    async function loadTemplates() {
        loading = true;
        try {
            // Would fetch from API
            templates = [...defaultTemplates];
        } finally {
            loading = false;
        }
    }
    
    function selectTemplate(template: Template) {
        selectedTemplate = template;
        editing = false;
    }
    
    function startEditing() {
        if (!selectedTemplate) return;
        editContent = selectedTemplate.content;
        editing = true;
    }
    
    function cancelEditing() {
        editing = false;
        editContent = '';
    }
    
    async function saveTemplate() {
        if (!selectedTemplate) return;
        
        selectedTemplate.content = editContent;
        selectedTemplate.lastModified = new Date().toISOString();
        templates = templates;
        editing = false;
        
        dispatch('save', { template: selectedTemplate });
    }
    
    function getTypeIcon(type: string): string {
        switch (type) {
            case 'spec': return '📋';
            case 'plan': return '📝';
            case 'tasks': return '✅';
            case 'checklist': return '☑️';
            default: return '📄';
        }
    }
    
    function getTypeColor(type: string): string {
        switch (type) {
            case 'spec': return '#4f46e5';
            case 'plan': return '#7c3aed';
            case 'tasks': return '#22c55e';
            case 'checklist': return '#eab308';
            default: return '#a0a0a0';
        }
    }
    
    loadTemplates();
</script>

<div class="manager">
    <div class="sidebar">
        <div class="sidebar-header">
            <h3>📑 Templates</h3>
        </div>
        
        {#if loading}
            <div class="loading">Loading...</div>
        {:else}
            <div class="template-list">
                {#each templates as template}
                    <button 
                        class="template-item"
                        class:selected={selectedTemplate?.id === template.id}
                        on:click={() => selectTemplate(template)}
                    >
                        <span class="type-icon">{getTypeIcon(template.type)}</span>
                        <div class="template-info">
                            <span class="name">{template.name}</span>
                            <span class="type" style="color: {getTypeColor(template.type)}">{template.type}</span>
                        </div>
                        {#if template.isDefault}
                            <span class="default-badge">DEFAULT</span>
                        {/if}
                    </button>
                {/each}
            </div>
        {/if}
    </div>
    
    <div class="content">
        {#if selectedTemplate}
            <div class="content-header">
                <div class="header-info">
                    <h4>{getTypeIcon(selectedTemplate.type)} {selectedTemplate.name}</h4>
                    <p class="description">{selectedTemplate.description}</p>
                </div>
                <div class="actions">
                    {#if editing}
                        <button class="btn secondary" on:click={cancelEditing}>Cancel</button>
                        <button class="btn primary" on:click={saveTemplate}>Save</button>
                    {:else}
                        <button class="btn primary" on:click={startEditing}>✏️ Edit</button>
                    {/if}
                </div>
            </div>
            
            {#if editing}
                <textarea 
                    class="editor"
                    bind:value={editContent}
                    spellcheck="false"
                ></textarea>
            {:else}
                <pre class="preview">{selectedTemplate.content}</pre>
            {/if}
            
            <div class="footer">
                <span>Last modified: {new Date(selectedTemplate.lastModified).toLocaleString()}</span>
                <span class="variables">Variables: {'{{variable_name}}'}</span>
            </div>
        {:else}
            <div class="empty">
                <div class="empty-icon">📑</div>
                <p>Select a template to view or edit</p>
            </div>
        {/if}
    </div>
</div>

<style>
    .manager {
        font-family: system-ui, sans-serif;
        display: flex;
        height: 500px;
        background: var(--bg-primary, #1a1a2e);
        border-radius: 8px;
        color: var(--text-primary, #e0e0e0);
        overflow: hidden;
    }
    
    .sidebar {
        width: 260px;
        border-right: 1px solid var(--border, #3d3d5c);
        display: flex;
        flex-direction: column;
    }
    
    .sidebar-header {
        padding: 1rem;
        border-bottom: 1px solid var(--border, #3d3d5c);
    }
    
    .sidebar-header h3 {
        margin: 0;
    }
    
    .template-list {
        flex: 1;
        overflow-y: auto;
        padding: 0.5rem;
    }
    
    .template-item {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        width: 100%;
        padding: 0.75rem;
        background: none;
        border: none;
        border-radius: 6px;
        color: var(--text-primary, #e0e0e0);
        cursor: pointer;
        text-align: left;
        transition: all 0.2s;
        margin-bottom: 0.25rem;
    }
    
    .template-item:hover {
        background: var(--bg-secondary, #2d2d44);
    }
    
    .template-item.selected {
        background: var(--accent, #4f46e5);
    }
    
    .type-icon {
        font-size: 1.5rem;
    }
    
    .template-info {
        flex: 1;
        display: flex;
        flex-direction: column;
        overflow: hidden;
    }
    
    .name {
        font-size: 0.9rem;
        font-weight: 500;
    }
    
    .type {
        font-size: 0.75rem;
        text-transform: uppercase;
    }
    
    .default-badge {
        padding: 0.125rem 0.375rem;
        background: rgba(255,255,255,0.1);
        border-radius: 4px;
        font-size: 0.6rem;
        font-weight: 600;
    }
    
    .content {
        flex: 1;
        display: flex;
        flex-direction: column;
        overflow: hidden;
    }
    
    .content-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        padding: 1rem;
        border-bottom: 1px solid var(--border, #3d3d5c);
    }
    
    .header-info h4 {
        margin: 0 0 0.25rem;
    }
    
    .description {
        margin: 0;
        font-size: 0.85rem;
        color: var(--text-secondary, #a0a0a0);
    }
    
    .actions {
        display: flex;
        gap: 0.5rem;
    }
    
    .btn {
        padding: 0.5rem 1rem;
        border: none;
        border-radius: 6px;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s;
    }
    
    .btn.primary {
        background: var(--accent, #4f46e5);
        color: white;
    }
    
    .btn.secondary {
        background: var(--bg-secondary, #2d2d44);
        color: var(--text-primary, #e0e0e0);
    }
    
    .editor, .preview {
        flex: 1;
        margin: 0;
        padding: 1rem;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.85rem;
        line-height: 1.6;
        overflow: auto;
        background: var(--bg-code, #0d0d17);
    }
    
    .editor {
        border: none;
        color: var(--text-primary, #e0e0e0);
        resize: none;
    }
    
    .editor:focus {
        outline: none;
    }
    
    .footer {
        display: flex;
        justify-content: space-between;
        padding: 0.5rem 1rem;
        font-size: 0.8rem;
        color: var(--text-secondary, #a0a0a0);
        background: var(--bg-secondary, #2d2d44);
    }
    
    .variables {
        font-family: monospace;
    }
    
    .loading, .empty {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        color: var(--text-secondary, #a0a0a0);
    }
    
    .empty-icon {
        font-size: 3rem;
        margin-bottom: 0.5rem;
    }
</style>
