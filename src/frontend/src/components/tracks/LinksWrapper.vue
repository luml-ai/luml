<template>
  <div class="content">
    <LinksToolbar />
    <LinksTable />
    <LinkArtifactEditor />
  </div>
</template>

<script setup lang="ts">
import LinkArtifactEditor from './LinkArtifactEditor.vue'
import LinksTable from './LinksTable.vue'
import LinksToolbar from './LinksToolbar.vue'
</script>

<style scoped>
.content {
  padding: 12px;
  border-radius: 8px;
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  overflow: hidden;
}

@media (min-width: 768px) {
  .content {
    margin: 0 -88px;
  }
}
</style>
