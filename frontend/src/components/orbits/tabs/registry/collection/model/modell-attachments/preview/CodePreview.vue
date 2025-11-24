<template>
  <div class="content-code">
    <pre><code>{{ textContent }}</code></pre>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  textContent: string
}>()
</script>

<style scoped>
.content-code {
  flex: 1;
  padding: 1rem;
  border-radius: 4px;
  overflow: auto;
  font-size: 0.9rem;
  line-height: 1.5;
  background: var(--surface-50);
}

.content-code pre {
  margin: 0;
}
</style>
