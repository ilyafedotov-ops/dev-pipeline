<script lang="ts">
  // Settings page for DevGodzilla configuration

  let apiUrl = 'http://192.168.1.227:8000';
  let saved = false;

  function saveSettings() {
    // In a real implementation, this would persist to localStorage or backend
    localStorage.setItem('devgodzilla_api_url', apiUrl);
    saved = true;
    setTimeout(() => saved = false, 2000);
  }
</script>

<svelte:head>
  <title>Settings - DevGodzilla</title>
</svelte:head>

<div class="settings-page">
  <h1 class="text-3xl font-bold text-gray-900 dark:text-white mb-8">Settings</h1>

  {#if saved}
    <div class="bg-green-100 dark:bg-green-900 border border-green-300 dark:border-green-700 rounded-lg p-4 mb-6">
      <p class="text-green-800 dark:text-green-200">Settings saved!</p>
    </div>
  {/if}

  <div class="space-y-6">
    <!-- API Configuration -->
    <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
      <h2 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">API Configuration</h2>
      
      <div class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            DevGodzilla API URL
          </label>
          <input
            type="text"
            bind:value={apiUrl}
            class="w-full max-w-md px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg 
                   bg-white dark:bg-gray-900 text-gray-900 dark:text-white"
          />
          <p class="mt-1 text-sm text-gray-500">The base URL for the DevGodzilla API server</p>
        </div>
      </div>
    </div>

    <!-- Default Behaviors -->
    <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
      <h2 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">Default Behaviors</h2>
      
      <div class="space-y-4">
        <label class="flex items-center gap-3">
          <input type="checkbox" class="w-4 h-4 text-indigo-600 rounded">
          <span class="text-gray-700 dark:text-gray-300">Auto-start protocols after creation</span>
        </label>
        
        <label class="flex items-center gap-3">
          <input type="checkbox" class="w-4 h-4 text-indigo-600 rounded" checked>
          <span class="text-gray-700 dark:text-gray-300">Show notifications for clarification requests</span>
        </label>
        
        <label class="flex items-center gap-3">
          <input type="checkbox" class="w-4 h-4 text-indigo-600 rounded" checked>
          <span class="text-gray-700 dark:text-gray-300">Require QA approval before step completion</span>
        </label>
      </div>
    </div>

    <!-- Constitution Defaults -->
    <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
      <h2 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">Constitution Defaults</h2>
      
      <div class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Default Classification
          </label>
          <select class="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg 
                        bg-white dark:bg-gray-900 text-gray-900 dark:text-white">
            <option value="default">Default</option>
            <option value="startup-fast">Startup Fast</option>
            <option value="team-standard">Team Standard</option>
            <option value="enterprise">Enterprise Compliance</option>
          </select>
        </div>
      </div>
    </div>

    <!-- Save Button -->
    <div class="flex justify-end">
      <button
        on:click={saveSettings}
        class="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
      >
        Save Settings
      </button>
    </div>
  </div>
</div>
