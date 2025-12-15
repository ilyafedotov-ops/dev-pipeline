<script lang="ts">
    // import { createEventDispatcher } from 'svelte'; // Unused
    // import { client, type UserStory } from './client';  // Unused
    
    // export let projectId: number; // Unused
    // export let specId: string = ''; // Unused for now
    
    // const dispatch = createEventDispatcher(); // Unused
    
    interface Story {
        id: string;
        title: string;
        status: 'pending' | 'in_progress' | 'completed' | 'blocked';
        priority: 'P1' | 'P2' | 'P3';
        tasks: Task[];
    }
    
    interface Task {
        id: string;
        name: string;
        status: 'pending' | 'completed' | 'failed';
    }
    
    let stories: Story[] = [];
    let loading = true;
    let filter: 'all' | 'pending' | 'in_progress' | 'completed' = 'all';
    
    $: filteredStories = stories.filter(s => 
        filter === 'all' || s.status === filter
    );
    
    $: progress = stories.length > 0
        ? Math.round((stories.filter(s => s.status === 'completed').length / stories.length) * 100)
        : 0;
    
    async function loadStories() {
        loading = true;
        try {
            // Mock data - would fetch from API
            stories = [
                {
                    id: 'US1',
                    title: 'User can log in with email/password',
                    status: 'completed',
                    priority: 'P1',
                    tasks: [
                        { id: 'T1', name: 'Create login form', status: 'completed' },
                        { id: 'T2', name: 'Add auth API', status: 'completed' },
                    ]
                },
                {
                    id: 'US2',
                    title: 'User can reset password',
                    status: 'in_progress',
                    priority: 'P1',
                    tasks: [
                        { id: 'T3', name: 'Create reset form', status: 'completed' },
                        { id: 'T4', name: 'Send reset email', status: 'pending' },
                    ]
                },
                {
                    id: 'US3',
                    title: 'User can view profile',
                    status: 'pending',
                    priority: 'P2',
                    tasks: []
                },
            ];
        } finally {
            loading = false;
        }
    }
    
    function getStatusIcon(status: string): string {
        switch (status) {
            case 'completed': return '✅';
            case 'in_progress': return '🔄';
            case 'blocked': return '🚫';
            default: return '⏳';
        }
    }
    
    function getPriorityColor(priority: string): string {
        switch (priority) {
            case 'P1': return 'var(--red-500, #ef4444)';
            case 'P2': return 'var(--yellow-500, #eab308)';
            default: return 'var(--green-500, #22c55e)';
        }
    }
    
    loadStories();
</script>

<div class="tracker">
    <div class="header">
        <h3>User Story Tracker</h3>
        <div class="progress-bar">
            <div class="progress-fill" style="width: {progress}%"></div>
            <span class="progress-text">{progress}% Complete</span>
        </div>
    </div>
    
    <div class="filters">
        <button class:active={filter === 'all'} on:click={() => filter = 'all'}>All</button>
        <button class:active={filter === 'pending'} on:click={() => filter = 'pending'}>Pending</button>
        <button class:active={filter === 'in_progress'} on:click={() => filter = 'in_progress'}>In Progress</button>
        <button class:active={filter === 'completed'} on:click={() => filter = 'completed'}>Completed</button>
    </div>
    
    {#if loading}
        <div class="loading">Loading stories...</div>
    {:else if filteredStories.length === 0}
        <div class="empty">No stories found</div>
    {:else}
        <div class="stories">
            {#each filteredStories as story}
                <div class="story" class:completed={story.status === 'completed'}>
                    <div class="story-header">
                        <span class="status-icon">{getStatusIcon(story.status)}</span>
                        <span class="priority" style="background: {getPriorityColor(story.priority)}">{story.priority}</span>
                        <span class="story-id">{story.id}</span>
                        <span class="story-title">{story.title}</span>
                    </div>
                    
                    {#if story.tasks.length > 0}
                        <div class="tasks">
                            {#each story.tasks as task}
                                <div class="task" class:completed={task.status === 'completed'}>
                                    <span class="task-checkbox">
                                        {task.status === 'completed' ? '☑' : '☐'}
                                    </span>
                                    <span class="task-name">{task.name}</span>
                                </div>
                            {/each}
                        </div>
                    {/if}
                </div>
            {/each}
        </div>
    {/if}
</div>

<style>
    .tracker {
        font-family: system-ui, sans-serif;
        padding: 1rem;
        background: var(--bg-primary, #1a1a2e);
        border-radius: 8px;
        color: var(--text-primary, #e0e0e0);
    }
    
    .header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1rem;
    }
    
    h3 {
        margin: 0;
        font-size: 1.2rem;
    }
    
    .progress-bar {
        position: relative;
        width: 200px;
        height: 24px;
        background: var(--bg-secondary, #2d2d44);
        border-radius: 12px;
        overflow: hidden;
    }
    
    .progress-fill {
        height: 100%;
        background: linear-gradient(90deg, #4f46e5, #7c3aed);
        transition: width 0.3s;
    }
    
    .progress-text {
        position: absolute;
        inset: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.75rem;
        font-weight: 600;
    }
    
    .filters {
        display: flex;
        gap: 0.5rem;
        margin-bottom: 1rem;
    }
    
    .filters button {
        padding: 0.5rem 1rem;
        border: none;
        background: var(--bg-secondary, #2d2d44);
        color: var(--text-secondary, #a0a0a0);
        border-radius: 4px;
        cursor: pointer;
        transition: all 0.2s;
    }
    
    .filters button:hover,
    .filters button.active {
        background: var(--accent, #4f46e5);
        color: white;
    }
    
    .stories {
        display: flex;
        flex-direction: column;
        gap: 0.75rem;
    }
    
    .story {
        background: var(--bg-secondary, #2d2d44);
        border-radius: 6px;
        padding: 0.75rem;
        border-left: 3px solid var(--accent, #4f46e5);
    }
    
    .story.completed {
        opacity: 0.7;
        border-left-color: var(--green-500, #22c55e);
    }
    
    .story-header {
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    .priority {
        padding: 0.125rem 0.375rem;
        border-radius: 4px;
        font-size: 0.7rem;
        font-weight: 600;
        color: white;
    }
    
    .story-id {
        font-weight: 600;
        color: var(--text-secondary, #a0a0a0);
    }
    
    .tasks {
        margin-top: 0.5rem;
        padding-left: 1.5rem;
    }
    
    .task {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        font-size: 0.9rem;
        color: var(--text-secondary, #a0a0a0);
    }
    
    .task.completed {
        text-decoration: line-through;
    }
    
    .loading, .empty {
        text-align: center;
        padding: 2rem;
        color: var(--text-secondary, #a0a0a0);
    }
</style>
