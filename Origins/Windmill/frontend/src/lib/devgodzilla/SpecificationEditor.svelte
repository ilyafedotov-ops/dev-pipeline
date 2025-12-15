<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  
  export let specContent = '';
  export let readOnly = false;
  
  const dispatch = createEventDispatcher();
  
  function handleInput(event: Event) {
    specContent = (event.target as HTMLTextAreaElement).value;
    dispatch('change', specContent);
  }
  
  function handleSave() {
    dispatch('save', specContent);
  }
</script>

<div class="spec-editor flex flex-col h-full border rounded-md overflow-hidden bg-gray-50 dark:bg-gray-900 border-gray-200 dark:border-gray-700">
  <div class="toolbar flex items-center justify-between px-4 py-2 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
    <div class="flex items-center space-x-2">
      <span class="font-semibold text-sm text-gray-700 dark:text-gray-300">Feature Specification</span>
      <span class="text-xs text-gray-500 bg-gray-100 dark:bg-gray-700 px-2 py-0.5 rounded">Markdown/YAML</span>
    </div>
    
    <div class="actions">
      {#if !readOnly}
        <button 
          on:click={handleSave}
          class="px-3 py-1.5 text-sm font-medium text-white bg-blue-600 rounded hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors"
        >
          Save Spec
        </button>
      {/if}
    </div>
  </div>
  
  <div class="editor-container flex-1 relative">
    <textarea
      value={specContent}
      on:input={handleInput}
      readonly={readOnly}
      class="w-full h-full p-4 font-mono text-sm resize-none bg-transparent focus:outline-none dark:text-gray-300"
      placeholder="# Feature Specification\n\nname: New Feature\ndescription: ...\n\n## Requirements\n- ..."
    ></textarea>
  </div>
</div>

<style>
  .spec-editor {
    min-height: 400px;
  }
</style>
