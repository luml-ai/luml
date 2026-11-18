<template>
  <div class="structure">
    <div class="tree">
      <ReferenceProfileJsonNode :value="document" />
    </div>
    <MCopyButton class="tree-copy" :text="code" :icon-size="14" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { formatReferenceDocument } from '@/utils/reference-profile'
import MCopyButton from '@/components/MCopyButton.vue'
import ReferenceProfileJsonNode from '@/components/reference-profile/ReferenceProfileJsonNode.vue'

interface Props {
  document: Record<string, unknown>
}

const props = defineProps<Props>()

const code = computed(() => formatReferenceDocument(props.document))
</script>

<style scoped>
.structure {
  position: relative;
  display: flex;
  height: 100%;
  min-height: 0;
  border: 1px solid var(--p-listbox-border-color);
  border-radius: var(--p-card-border-radius);
  background: var(--p-listbox-option-focus-background);
}

.tree {
  flex: 1;
  min-width: 0;
  padding: 8px 40px 8px 8px;
  overflow: auto;
  font-family: Consolas, 'SFMono-Regular', Menlo, monospace;
  font-size: 14px;
}

.tree-copy {
  position: absolute;
  top: 8px;
  right: 8px;
}
</style>
