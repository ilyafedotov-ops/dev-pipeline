<script lang="ts">
  import { onMount } from 'svelte';
  import { devGodzilla, type Project, type ProtocolRun } from '$lib/devgodzilla/client';

  let projects: Project[] = [];
  let recentProtocols: ProtocolRun[] = [];
  let loading = true;
  let error: string | null = null;

  // Stats
  let stats = {
    totalProjects: 0,
    activeProtocols: 0,
    completedToday: 0,
    pendingClarifications: 0
  };

  onMount(async () => {
    try {
      // Load projects
      projects = await devGodzilla.listProjects();
      stats.totalProjects = projects.length;

      // Load recent protocols (from all projects)
      const allProtocols: ProtocolRun[] = [];
      for (const project of projects.slice(0, 5)) {
        const protocols = await devGodzilla.listProtocols(project.id);
        allProtocols.push(...protocols);
      }
      recentProtocols = allProtocols
        .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
        .slice(0, 10);

      stats.activeProtocols = allProtocols.filter(p => p.status === 'running').length;
      stats.completedToday = allProtocols.filter(p => {
        const today = new Date().toDateString();
        return p.status === 'completed' && new Date(p.created_at).toDateString() === today;
      }).length;

    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load dashboard data';
    } finally {
      loading = false;
    }
  });
</script>

<svelte:head>
  <title>DevGodzilla - Dashboard</title>
</svelte:head>

<div class="dashboard">
  <h1 class="text-3xl font-bold text-gray-900 dark:text-white mb-8">Dashboard</h1>

  {#if error}
    <div class="bg-red-100 dark:bg-red-900 border border-red-300 dark:border-red-700 rounded-lg p-4 mb-6">
      <p class="text-red-800 dark:text-red-200">{error}</p>
    </div>
  {/if}

  <!-- Stats Cards -->
  <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
    <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm p-6 border border-gray-200 dark:border-gray-700">
      <div class="flex items-center justify-between">
        <div>
          <p class="text-sm text-gray-500 dark:text-gray-400">Total Projects</p>
          <p class="text-3xl font-bold text-gray-900 dark:text-white">{stats.totalProjects}</p>
        </div>
        <span class="text-3xl">📁</span>
      </div>
    </div>

    <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm p-6 border border-gray-200 dark:border-gray-700">
      <div class="flex items-center justify-between">
        <div>
          <p class="text-sm text-gray-500 dark:text-gray-400">Active Protocols</p>
          <p class="text-3xl font-bold text-indigo-600 dark:text-indigo-400">{stats.activeProtocols}</p>
        </div>
        <span class="text-3xl">⚡</span>
      </div>
    </div>

    <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm p-6 border border-gray-200 dark:border-gray-700">
      <div class="flex items-center justify-between">
        <div>
          <p class="text-sm text-gray-500 dark:text-gray-400">Completed Today</p>
          <p class="text-3xl font-bold text-green-600 dark:text-green-400">{stats.completedToday}</p>
        </div>
        <span class="text-3xl">✅</span>
      </div>
    </div>

    <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm p-6 border border-gray-200 dark:border-gray-700">
      <div class="flex items-center justify-between">
        <div>
          <p class="text-sm text-gray-500 dark:text-gray-400">Pending Clarifications</p>
          <p class="text-3xl font-bold text-amber-600 dark:text-amber-400">{stats.pendingClarifications}</p>
        </div>
        <span class="text-3xl">❓</span>
      </div>
    </div>
  </div>

  <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
    <!-- Recent Projects -->
    <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700">
      <div class="p-6 border-b border-gray-200 dark:border-gray-700 flex justify-between items-center">
        <h2 class="text-lg font-semibold text-gray-900 dark:text-white">Recent Projects</h2>
        <a href="/devgodzilla/projects" class="text-sm text-indigo-600 hover:text-indigo-700">View all →</a>
      </div>
      <div class="divide-y divide-gray-200 dark:divide-gray-700">
        {#if loading}
          <div class="p-6 text-center text-gray-500">Loading...</div>
        {:else if projects.length === 0}
          <div class="p-6 text-center text-gray-500">
            No projects yet. 
            <a href="/devgodzilla/projects/new" class="text-indigo-600 hover:underline">Create one</a>
          </div>
        {:else}
          {#each projects.slice(0, 5) as project}
            <a 
              href="/devgodzilla/projects/{project.id}" 
              class="block p-4 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
            >
              <div class="flex justify-between items-center">
                <div>
                  <p class="font-medium text-gray-900 dark:text-white">{project.name}</p>
                  <p class="text-sm text-gray-500 dark:text-gray-400">{project.git_url || 'No repository'}</p>
                </div>
                <span class="text-gray-400">→</span>
              </div>
            </a>
          {/each}
        {/if}
      </div>
    </div>

    <!-- Recent Protocols -->
    <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700">
      <div class="p-6 border-b border-gray-200 dark:border-gray-700 flex justify-between items-center">
        <h2 class="text-lg font-semibold text-gray-900 dark:text-white">Recent Protocols</h2>
        <a href="/devgodzilla/protocols" class="text-sm text-indigo-600 hover:text-indigo-700">View all →</a>
      </div>
      <div class="divide-y divide-gray-200 dark:divide-gray-700">
        {#if loading}
          <div class="p-6 text-center text-gray-500">Loading...</div>
        {:else if recentProtocols.length === 0}
          <div class="p-6 text-center text-gray-500">No protocol runs yet</div>
        {:else}
          {#each recentProtocols.slice(0, 5) as protocol}
            <a 
              href="/devgodzilla/protocols/{protocol.id}" 
              class="block p-4 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
            >
              <div class="flex justify-between items-center">
                <div>
                  <p class="font-medium text-gray-900 dark:text-white">{protocol.protocol_name}</p>
                  <p class="text-sm text-gray-500 dark:text-gray-400">
                    {new Date(protocol.created_at).toLocaleDateString()}
                  </p>
                </div>
                <span class="px-2 py-1 text-xs rounded-full
                  {protocol.status === 'completed' ? 'bg-green-100 text-green-800' :
                   protocol.status === 'running' ? 'bg-blue-100 text-blue-800' :
                   protocol.status === 'failed' ? 'bg-red-100 text-red-800' :
                   'bg-gray-100 text-gray-800'}">
                  {protocol.status}
                </span>
              </div>
            </a>
          {/each}
        {/if}
      </div>
    </div>
  </div>

  <!-- Quick Actions -->
  <div class="mt-8">
    <h2 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">Quick Actions</h2>
    <div class="flex flex-wrap gap-4">
      <a 
        href="/devgodzilla/projects/new" 
        class="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
      >
        + New Project
      </a>
      <a 
        href="/devgodzilla/agents" 
        class="px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-800 dark:text-gray-200 rounded-lg hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors"
      >
        Configure Agents
      </a>
    </div>
  </div>
</div>
