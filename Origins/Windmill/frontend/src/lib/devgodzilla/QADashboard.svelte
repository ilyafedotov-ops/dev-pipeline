<script lang="ts">
  export let qaResult: {
    verdict: 'passed' | 'failed' | 'warning';
    summary: string;
    gates: Array<{
      id: string;
      name: string;
      status: 'passed' | 'failed' | 'skipped' | 'warning';
      findings: Array<{
        severity: string;
        message: string;
        file?: string;
        line?: number;
      }>;
    }>;
  } | null = null;
</script>

<div class="qa-dashboard bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm overflow-hidden">
  <div class="header px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex justify-between items-center bg-gray-50 dark:bg-gray-900">
    <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wider">Quality Assurance Report</h3>
    {#if qaResult}
      <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium 
        {qaResult.verdict === 'passed' ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200' : 
         qaResult.verdict === 'failed' ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200' : 
         'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'}">
        {qaResult.verdict.toUpperCase()}
      </span>
    {/if}
  </div>

  <div class="content p-4">
    {#if !qaResult}
      <div class="text-center text-gray-500 py-4">No QA results available</div>
    {:else}
      <div class="mb-4">
        <p class="text-sm text-gray-600 dark:text-gray-300">{qaResult.summary}</p>
      </div>

      <div class="gates space-y-4">
        {#each qaResult.gates as gate}
          <div class="gate border rounded-md border-gray-200 dark:border-gray-700 overflow-hidden">
            <div class="gate-header px-3 py-2 bg-gray-50 dark:bg-gray-800 flex justify-between items-center">
              <span class="font-medium text-sm text-gray-700 dark:text-gray-200">{gate.name}</span>
              <span class="text-xs font-mono 
                {gate.status === 'passed' ? 'text-green-600 dark:text-green-400' : 
                 gate.status === 'failed' ? 'text-red-600 dark:text-red-400' : 'text-gray-500'}">
                {gate.status.toUpperCase()}
              </span>
            </div>
            
            {#if gate.findings.length > 0}
              <div class="findings border-t border-gray-200 dark:border-gray-700">
                {#each gate.findings as finding}
                  <div class="finding px-3 py-2 border-b border-gray-100 dark:border-gray-800 last:border-0 flex items-start space-x-2 text-sm">
                    <span class="flex-shrink-0 mt-0.5">
                      {#if finding.severity === 'error'}
                        <svg class="w-4 h-4 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                      {:else}
                         <svg class="w-4 h-4 text-yellow-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
                      {/if}
                    </span>
                    <div class="flex-1">
                      <p class="text-gray-800 dark:text-gray-200">{finding.message}</p>
                      {#if finding.file}
                        <p class="text-xs text-gray-500 mt-0.5 font-mono">{finding.file}{#if finding.line}:{finding.line}{/if}</p>
                      {/if}
                    </div>
                  </div>
                {/each}
              </div>
            {/if}
          </div>
        {/each}
      </div>
    {/if}
  </div>
</div>
