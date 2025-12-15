<script lang="ts">
  import { onMount } from 'svelte';
  import { devGodzilla, type Project } from '$lib/devgodzilla/client';
  import QADashboard from '$lib/devgodzilla/QADashboard.svelte';

  let projects: Project[] = [];
  let loading = true;
  let error: string | null = null;

  // Placeholder QA stats
  let qaStats = {
    totalChecks: 0,
    passed: 0,
    warnings: 0,
    failed: 0
  };

  onMount(async () => {
    try {
      projects = await devGodzilla.listProjects();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load data';
    } finally {
      loading = false;
    }
  });
</script>

<svelte:head>
  <title>Quality - DevGodzilla</title>
</svelte:head>

<div class="quality-page">
  <h1 class="text-3xl font-bold text-gray-900 dark:text-white mb-8">Quality Assurance</h1>

  {#if error}
    <div class="bg-red-100 dark:bg-red-900 border border-red-300 dark:border-red-700 rounded-lg p-4 mb-6">
      <p class="text-red-800 dark:text-red-200">{error}</p>
    </div>
  {/if}

  <!-- QA Overview Stats -->
  <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
    <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm p-6 border border-gray-200 dark:border-gray-700">
      <p class="text-sm text-gray-500 dark:text-gray-400">Total Checks</p>
      <p class="text-3xl font-bold text-gray-900 dark:text-white">{qaStats.totalChecks}</p>
    </div>
    <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm p-6 border border-gray-200 dark:border-gray-700">
      <p class="text-sm text-gray-500 dark:text-gray-400">Passed</p>
      <p class="text-3xl font-bold text-green-600">{qaStats.passed}</p>
    </div>
    <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm p-6 border border-gray-200 dark:border-gray-700">
      <p class="text-sm text-gray-500 dark:text-gray-400">Warnings</p>
      <p class="text-3xl font-bold text-amber-600">{qaStats.warnings}</p>
    </div>
    <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm p-6 border border-gray-200 dark:border-gray-700">
      <p class="text-sm text-gray-500 dark:text-gray-400">Failed</p>
      <p class="text-3xl font-bold text-red-600">{qaStats.failed}</p>
    </div>
  </div>

  <!-- Constitutional Gates -->
  <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6 mb-8">
    <h2 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">Constitutional Gates</h2>
    <p class="text-gray-500 dark:text-gray-400">
      Quality gates are checked against each step output to ensure compliance with project constitution.
    </p>
    
    <div class="mt-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <div class="p-4 border border-gray-200 dark:border-gray-700 rounded-lg">
        <div class="flex items-center gap-2 mb-2">
          <span class="text-green-500">✓</span>
          <span class="font-medium text-gray-900 dark:text-white">Article III: Test-First</span>
        </div>
        <p class="text-sm text-gray-500">Tests must exist before implementation</p>
      </div>
      
      <div class="p-4 border border-gray-200 dark:border-gray-700 rounded-lg">
        <div class="flex items-center gap-2 mb-2">
          <span class="text-green-500">✓</span>
          <span class="font-medium text-gray-900 dark:text-white">Article VII: Simplicity</span>
        </div>
        <p class="text-sm text-gray-500">No unnecessary complexity</p>
      </div>
      
      <div class="p-4 border border-gray-200 dark:border-gray-700 rounded-lg">
        <div class="flex items-center gap-2 mb-2">
          <span class="text-green-500">✓</span>
          <span class="font-medium text-gray-900 dark:text-white">Article IX: Integration</span>
        </div>
        <p class="text-sm text-gray-500">Integration tests required</p>
      </div>
    </div>
  </div>

  <!-- Recent QA Results -->
  <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700">
    <div class="p-6 border-b border-gray-200 dark:border-gray-700">
      <h2 class="text-lg font-semibold text-gray-900 dark:text-white">Recent QA Results</h2>
    </div>
    <div class="p-6 text-center text-gray-500">
      No QA results yet. Results will appear here after protocol steps are executed.
    </div>
  </div>
</div>
