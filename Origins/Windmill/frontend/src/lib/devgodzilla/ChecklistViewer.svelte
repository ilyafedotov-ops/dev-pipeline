<script lang="ts">
    import { createEventDispatcher } from 'svelte';
    
    // export let stepId: number = 0; // Unused
    export let checklistItems: ChecklistItem[] = [];
    
    const dispatch = createEventDispatcher();
    
    interface ChecklistItem {
        id: string;
        text: string;
        category: 'required' | 'recommended' | 'optional';
        checked: boolean;
        autoVerified?: boolean;
        verificationNote?: string;
    }
    
    // Default checklist if none provided
    $: items = checklistItems.length ? checklistItems : [
        { id: '1', text: 'Document public APIs', category: 'required' as const, checked: true, autoVerified: true },
        { id: '2', text: 'Add unit tests for new logic', category: 'required' as const, checked: false, autoVerified: true },
        { id: '3', text: 'Update architecture diagrams', category: 'recommended' as const, checked: false, autoVerified: false },
        { id: '4', text: 'Add performance benchmarks', category: 'optional' as const, checked: false, autoVerified: false },
        { id: '5', text: 'Security scan passes', category: 'recommended' as const, checked: true, autoVerified: true },
        { id: '6', text: 'Code reviewed', category: 'recommended' as const, checked: false, autoVerified: false },
        { id: '7', text: 'Performance tested', category: 'optional' as const, checked: false, autoVerified: false },
    ];
    
    $: requiredItems = items.filter(i => i.category === 'required');
    $: recommendedItems = items.filter(i => i.category === 'recommended');
    $: optionalItems = items.filter(i => i.category === 'optional');
    
    $: requiredComplete = requiredItems.every(i => i.checked);
    $: progress = Math.round((items.filter(i => i.checked).length / items.length) * 100);
    
    function toggleItem(item: ChecklistItem) {
        if (item.autoVerified) return; // Can't toggle auto-verified items
        item.checked = !item.checked;
        items = items;
        dispatch('change', { id: item.id, checked: item.checked });
    }
    
    /* function getCategoryColor(category: string): string { // Unused
        switch (category) {
            case 'required': return '#ef4444';
            case 'recommended': return '#eab308';
            default: return '#22c55e';
        }
    } */
</script>

<div class="checklist">
    <div class="header">
        <h3>📋 QA Checklist</h3>
        <div class="progress-indicator" class:ready={requiredComplete}>
            {requiredComplete ? '✅ Ready' : '⏳ Pending'}
        </div>
    </div>
    
    <div class="progress-bar">
        <div class="progress-fill" style="width: {progress}%"></div>
    </div>
    
    {#if requiredItems.length > 0}
        <div class="category">
            <h4><span class="dot" style="background: #ef4444"></span> Required</h4>
            {#each requiredItems as item}
                <label 
                    class="item" 
                    class:checked={item.checked}
                    class:auto={item.autoVerified}
                >
                    <input 
                        type="checkbox" 
                        checked={item.checked}
                        disabled={item.autoVerified}
                        on:change={() => toggleItem(item)}
                    />
                    <span class="checkbox-custom">
                        {item.checked ? '✓' : ''}
                    </span>
                    <span class="item-text">{item.text}</span>
                    {#if item.autoVerified}
                        <span class="auto-badge">AUTO</span>
                    {/if}
                </label>
            {/each}
        </div>
    {/if}
    
    {#if recommendedItems.length > 0}
        <div class="category">
            <h4><span class="dot" style="background: #eab308"></span> Recommended</h4>
            {#each recommendedItems as item}
                <label 
                    class="item" 
                    class:checked={item.checked}
                    class:auto={item.autoVerified}
                >
                    <input 
                        type="checkbox" 
                        checked={item.checked}
                        disabled={item.autoVerified}
                        on:change={() => toggleItem(item)}
                    />
                    <span class="checkbox-custom">
                        {item.checked ? '✓' : ''}
                    </span>
                    <span class="item-text">{item.text}</span>
                    {#if item.autoVerified}
                        <span class="auto-badge">AUTO</span>
                    {/if}
                </label>
            {/each}
        </div>
    {/if}
    
    {#if optionalItems.length > 0}
        <div class="category">
            <h4><span class="dot" style="background: #22c55e"></span> Optional</h4>
            {#each optionalItems as item}
                <label 
                    class="item" 
                    class:checked={item.checked}
                    class:auto={item.autoVerified}
                >
                    <input 
                        type="checkbox" 
                        checked={item.checked}
                        disabled={item.autoVerified}
                        on:change={() => toggleItem(item)}
                    />
                    <span class="checkbox-custom">
                        {item.checked ? '✓' : ''}
                    </span>
                    <span class="item-text">{item.text}</span>
                    {#if item.autoVerified}
                        <span class="auto-badge">AUTO</span>
                    {/if}
                </label>
            {/each}
        </div>
    {/if}
    
    <div class="summary">
        {items.filter(i => i.checked).length} / {items.length} complete
    </div>
</div>

<style>
    .checklist {
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
        margin-bottom: 0.75rem;
    }
    
    h3 {
        margin: 0;
    }
    
    .progress-indicator {
        padding: 0.25rem 0.75rem;
        background: var(--bg-secondary, #2d2d44);
        border-radius: 12px;
        font-size: 0.8rem;
        color: var(--text-secondary, #a0a0a0);
    }
    
    .progress-indicator.ready {
        background: rgba(34, 197, 94, 0.2);
        color: #22c55e;
    }
    
    .progress-bar {
        height: 4px;
        background: var(--bg-secondary, #2d2d44);
        border-radius: 2px;
        margin-bottom: 1rem;
        overflow: hidden;
    }
    
    .progress-fill {
        height: 100%;
        background: linear-gradient(90deg, #4f46e5, #7c3aed);
        transition: width 0.3s;
    }
    
    .category {
        margin-bottom: 1rem;
    }
    
    h4 {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin: 0 0 0.5rem;
        font-size: 0.85rem;
        color: var(--text-secondary, #a0a0a0);
    }
    
    .dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
    }
    
    .item {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.5rem 0.75rem;
        background: var(--bg-secondary, #2d2d44);
        border-radius: 6px;
        margin-bottom: 0.25rem;
        cursor: pointer;
        transition: all 0.2s;
    }
    
    .item:hover {
        background: var(--bg-hover, #3d3d5c);
    }
    
    .item.checked {
        opacity: 0.7;
    }
    
    .item.auto {
        cursor: default;
    }
    
    .item input {
        display: none;
    }
    
    .checkbox-custom {
        width: 20px;
        height: 20px;
        border: 2px solid var(--text-secondary, #a0a0a0);
        border-radius: 4px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.75rem;
        transition: all 0.2s;
    }
    
    .item.checked .checkbox-custom {
        background: #22c55e;
        border-color: #22c55e;
        color: white;
    }
    
    .item-text {
        flex: 1;
    }
    
    .item.checked .item-text {
        text-decoration: line-through;
    }
    
    .auto-badge {
        padding: 0.125rem 0.375rem;
        background: rgba(79, 70, 229, 0.3);
        border-radius: 4px;
        font-size: 0.65rem;
        font-weight: 600;
        color: var(--accent, #4f46e5);
    }
    
    .summary {
        text-align: center;
        font-size: 0.85rem;
        color: var(--text-secondary, #a0a0a0);
        margin-top: 0.5rem;
    }
</style>
