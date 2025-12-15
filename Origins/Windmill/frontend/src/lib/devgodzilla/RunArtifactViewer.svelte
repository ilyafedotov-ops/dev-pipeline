<script lang="ts">
    import { createEventDispatcher } from 'svelte';
    
    // export let stepId: number = 0; // Unused
    export let artifacts: Artifact[] = [];
    
    const dispatch = createEventDispatcher();
    
    interface Artifact {
        id: string;
        type: 'log' | 'diff' | 'file' | 'report' | 'test';
        name: string;
        size: number;
        createdAt: string;
        content?: string;
    }
    
    let selectedArtifact: Artifact | null = null;
    let loading = false;
    
    // Default artifacts if none provided
    $: items = artifacts.length ? artifacts : [
        { id: '1', type: 'log' as const, name: 'execution.log', size: 12450, createdAt: '2024-01-15T10:30:00Z' },
        { id: '2', type: 'diff' as const, name: 'changes.diff', size: 3200, createdAt: '2024-01-15T10:31:00Z' },
        { id: '3', type: 'file' as const, name: 'output.json', size: 850, createdAt: '2024-01-15T10:31:30Z' },
        { id: '4', type: 'report' as const, name: 'quality-report.md', size: 2100, createdAt: '2024-01-15T10:32:00Z' },
        { id: '5', type: 'test' as const, name: 'test-results.xml', size: 5600, createdAt: '2024-01-15T10:33:00Z' },
    ];
    
    async function viewArtifact(artifact: Artifact) {
        selectedArtifact = artifact;
        loading = true;
        
        try {
            // Simulate loading content
            await new Promise(r => setTimeout(r, 500));
            
            // Mock content based on type
            if (artifact.type === 'log') {
                artifact.content = `[10:30:00] Starting execution...
[10:30:01] Loading workspace at /home/user/project
[10:30:02] Running agent: opencode
[10:30:15] Agent completed with 3 file changes
[10:30:16] Running QA gates...
[10:30:45] LintGate: PASS (0 issues)
[10:30:50] TypeGate: PASS
[10:31:00] TestGate: PASS (15 tests)
[10:31:00] Execution complete!`;
            } else if (artifact.type === 'diff') {
                artifact.content = `diff --git a/src/auth.py b/src/auth.py
--- a/src/auth.py
+++ b/src/auth.py
@@ -12,6 +12,15 @@ def login(username, password):
     user = get_user(username)
     if not user:
         return None
+    
+    if not verify_password(password, user.password_hash):
+        log_failed_attempt(username)
+        return None
+    
+    session = create_session(user)
+    return session.token

 def logout(session_id):
     invalidate_session(session_id)`;
            } else if (artifact.type === 'report') {
                artifact.content = `# Quality Report

## Summary
- **Verdict:** PASS
- **Duration:** 45.2s
- **Gates:** 3/3 passed

## Gate Results

### ✅ LintGate
No issues found.

### ✅ TypeGate  
No type errors.

### ✅ TestGate
15/15 tests passed.`;
            } else {
                artifact.content = `// Content of ${artifact.name}
// ${artifact.size} bytes`;
            }
        } finally {
            loading = false;
        }
    }
    
    function getTypeIcon(type: string): string {
        switch (type) {
            case 'log': return '📜';
            case 'diff': return '📝';
            case 'file': return '📄';
            case 'report': return '📊';
            case 'test': return '🧪';
            default: return '📁';
        }
    }
    
    function formatSize(bytes: number): string {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    }
    
    function formatDate(dateStr: string): string {
        return new Date(dateStr).toLocaleString();
    }
    
    function downloadArtifact(artifact: Artifact) {
        dispatch('download', { artifact });
    }
</script>

<div class="viewer">
    <div class="sidebar">
        <h3>📦 Artifacts</h3>
        <div class="artifact-list">
            {#each items as artifact}
                <button 
                    class="artifact-item"
                    class:selected={selectedArtifact?.id === artifact.id}
                    on:click={() => viewArtifact(artifact)}
                >
                    <span class="type-icon">{getTypeIcon(artifact.type)}</span>
                    <div class="artifact-info">
                        <span class="name">{artifact.name}</span>
                        <span class="meta">{formatSize(artifact.size)}</span>
                    </div>
                </button>
            {/each}
        </div>
    </div>
    
    <div class="content">
        {#if loading}
            <div class="loading">Loading...</div>
        {:else if selectedArtifact}
            <div class="content-header">
                <h4>{getTypeIcon(selectedArtifact.type)} {selectedArtifact.name}</h4>
                <div class="actions">
                    <button class="btn-small" on:click={() => selectedArtifact && downloadArtifact(selectedArtifact)}>
                        ⬇️ Download
                    </button>
                </div>
            </div>
            <div class="content-meta">
                <span>Size: {formatSize(selectedArtifact.size)}</span>
                <span>Created: {formatDate(selectedArtifact.createdAt)}</span>
            </div>
            <pre class="content-body" 
                 class:diff={selectedArtifact.type === 'diff'}
                 class:log={selectedArtifact.type === 'log'}
                 class:markdown={selectedArtifact.type === 'report'}
            >{selectedArtifact.content || 'No content'}</pre>
        {:else}
            <div class="empty">
                <div class="empty-icon">📂</div>
                <p>Select an artifact to view</p>
            </div>
        {/if}
    </div>
</div>

<style>
    .viewer {
        font-family: system-ui, sans-serif;
        display: flex;
        height: 400px;
        background: var(--bg-primary, #1a1a2e);
        border-radius: 8px;
        color: var(--text-primary, #e0e0e0);
        overflow: hidden;
    }
    
    .sidebar {
        width: 240px;
        border-right: 1px solid var(--border, #3d3d5c);
        display: flex;
        flex-direction: column;
    }
    
    .sidebar h3 {
        margin: 0;
        padding: 1rem;
        font-size: 1rem;
    }
    
    .artifact-list {
        flex: 1;
        overflow-y: auto;
        padding: 0 0.5rem 0.5rem;
    }
    
    .artifact-item {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        width: 100%;
        padding: 0.5rem;
        background: none;
        border: none;
        border-radius: 6px;
        color: var(--text-primary, #e0e0e0);
        cursor: pointer;
        text-align: left;
        transition: all 0.2s;
    }
    
    .artifact-item:hover {
        background: var(--bg-secondary, #2d2d44);
    }
    
    .artifact-item.selected {
        background: var(--accent, #4f46e5);
    }
    
    .type-icon {
        font-size: 1.25rem;
    }
    
    .artifact-info {
        display: flex;
        flex-direction: column;
        overflow: hidden;
    }
    
    .name {
        font-size: 0.9rem;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    
    .meta {
        font-size: 0.75rem;
        color: var(--text-secondary, #a0a0a0);
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
        align-items: center;
        padding: 1rem;
        border-bottom: 1px solid var(--border, #3d3d5c);
    }
    
    .content-header h4 {
        margin: 0;
    }
    
    .content-meta {
        display: flex;
        gap: 1rem;
        padding: 0.5rem 1rem;
        font-size: 0.8rem;
        color: var(--text-secondary, #a0a0a0);
        background: var(--bg-secondary, #2d2d44);
    }
    
    .content-body {
        flex: 1;
        margin: 0;
        padding: 1rem;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.85rem;
        line-height: 1.5;
        overflow: auto;
        background: var(--bg-code, #0d0d17);
    }
    
    .content-body.diff {
        color: var(--text-primary, #e0e0e0);
    }
    
    .content-body.log {
        color: #22c55e;
    }
    
    .btn-small {
        padding: 0.25rem 0.5rem;
        background: var(--bg-secondary, #2d2d44);
        border: none;
        border-radius: 4px;
        color: var(--text-primary, #e0e0e0);
        cursor: pointer;
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
