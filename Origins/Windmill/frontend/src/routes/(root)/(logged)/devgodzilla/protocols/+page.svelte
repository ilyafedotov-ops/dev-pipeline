<script lang="ts">
  import { onMount } from 'svelte';
  import { devGodzilla, type Project, type ProtocolRun } from '$lib/devgodzilla/client';

  let protocols: ProtocolRun[] = [];
  let projects: Project[] = [];
  let loading = true;
  let error: string | null = null;
  let filterStatus = '';

  $: filteredProtocols = filterStatus 
    ? protocols.filter(p => p.status === filterStatus)
    : protocols;

  onMount(async () => {
    try {
      projects = await devGodzilla.listProjects();
      
      // Load protocols from all projects
      const allProtocols: ProtocolRun[] = [];
      for (const project of projects) {
        const projectProtocols = await devGodzilla.listProtocols(project.id);
        allProtocols.push(...projectProtocols);
      }
      protocols = allProtocols.sort((a, b) => 
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load protocols';
    } finally {
      loading = false;
    }
  });

  function getProjectName(projectId: number): string {
    const project = projects.find(p => p.id === projectId);
    return project?.name || `Project #${projectId}`;
  }
</script>

<svelte:head>
  <title>Protocols - DevGodzilla</title>
</svelte:head>

<div class="protocols-page">
  <div class="flex justify-between items-center mb-6">
    <h1 class="text-3xl font-bold text-gray-900 dark:text-white">Protocols</h1>
  </div>

  <!-- Filters -->
  <div class="flex gap-4 mb-6">
    <select
      bind:value={filterStatus}
      class="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg 
             bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
    >
      <option value="">All Statuses</option>
      <option value="pending">Pending</option>
      <option value="running">Running</option>
      <option value="completed">Completed</option>
      <option value="failed">Failed</option>
      <option value="cancelled">Cancelled</option>
    </select>
  </div>

  {#if error}
    <div class="bg-red-100 dark:bg-red-900 border border-red-300 dark:border-red-700 rounded-lg p-4 mb-6">
      <p class="text-red-800 dark:text-red-200">{error}</p>
    </div>
  {/if}

  {#if loading}
    <div class="text-center py-12 text-gray-500">Loading protocols...</div>
  {:else if filteredProtocols.length === 0}
    <div class="text-center py-12 text-gray-500">
      {filterStatus ? 'No protocols with this status' : 'No protocols yet'}
    </div>
  {:else}
    <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
      <table class="w-full">
        <thead class="bg-gray-50 dark:bg-gray-900">
          <tr>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Project</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Created</th>
            <th class="px-6 py-3"></th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-200 dark:divide-gray-700">
          {#each filteredProtocols as protocol}
            <tr class="hover:bg-gray-50 dark:hover:bg-gray-700">
              <td class="px-6 py-4">
                <a href="/devgodzilla/protocols/{protocol.id}" class="font-medium text-indigo-600 hover:text-indigo-800">
                  {protocol.protocol_name}
                </a>
              </td>
              <td class="px-6 py-4 text-gray-500 dark:text-gray-400">
                <a href="/devgodzilla/projects/{protocol.project_id}" class="hover:text-indigo-600">
                  {getProjectName(protocol.project_id)}
                </a>
              </td>
              <td class="px-6 py-4">
                <span class="px-2 py-1 text-xs rounded-full
                  {protocol.status === 'completed' ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200' :
                   protocol.status === 'running' ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200' :
                   protocol.status === 'failed' ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200' :
                   'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'}">
                  {protocol.status}
                </span>
              </td>
              <td class="px-6 py-4 text-gray-500 dark:text-gray-400 text-sm">
                {new Date(protocol.created_at).toLocaleString()}
              </td>
              <td class="px-6 py-4 text-right">
                <a href="/devgodzilla/protocols/{protocol.id}" class="text-gray-400 hover:text-gray-600">
                  →
                </a>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>
