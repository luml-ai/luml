<script setup lang="ts">
import { ref, watch } from 'vue'
import { Dialog, Button } from 'primevue'
import { Check } from 'lucide-vue-next'
import type { MergePreview } from '@/lib/api/data-agent/data-agent.interfaces'
import { api } from '@/lib/api'

const props = defineProps<{
  visible: boolean
  kind: 'task' | 'run'
  itemId: string
}>()

const emit = defineEmits<{
  close: []
  merged: []
}>()

const preview = ref<MergePreview | null>(null)
const loading = ref(false)
const error = ref('')

watch(
  () => props.visible,
  async (isVisible) => {
    if (isVisible) {
      loading.value = true
      error.value = ''
      try {
        preview.value = props.kind === 'task'
          ? await api.dataAgent.getMergePreview(props.itemId)
          : await api.dataAgent.getRunMergePreview(props.itemId)
      } catch (e: any) {
        error.value = e?.response?.data?.detail ?? 'Failed to load preview'
      } finally {
        loading.value = false
      }
    } else {
      preview.value = null
    }
  },
)

async function confirmMerge() {
  error.value = ''
  try {
    if (props.kind === 'task') {
      await api.dataAgent.mergeTask(props.itemId)
    } else {
      await api.dataAgent.mergeRun(props.itemId)
    }
    emit('merged')
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Merge failed'
  }
}
</script>

<template>
  <Dialog
    :visible="visible"
    :header="kind === 'task' ? 'Merge Branch' : 'Merge Best Branch'"
    modal
    :style="{ width: '500px' }"
    @update:visible="!$event && emit('close')"
  >
    <div v-if="loading" class="loading">Loading preview...</div>
    <div v-else-if="preview" class="preview">
      <div class="branch-block">
        <span class="branch-label">Branch</span>
        <code class="branch-name">{{ preview.branch }}</code>
      </div>
      <div class="branch-block">
        <span class="branch-label">Into</span>
        <code class="branch-name">{{ preview.base_branch }}</code>
      </div>
      <div class="stats-grid">
        <div class="stat-row">
          <span>Commits</span>
          <strong>{{ preview.stats.commits_ahead }}</strong>
        </div>
        <div class="stat-row">
          <span>Files changed</span>
          <strong>{{ preview.stats.files_changed }}</strong>
        </div>
        <div class="stat-row">
          <span>Insertions</span>
          <strong class="ins">+{{ preview.stats.insertions }}</strong>
        </div>
        <div class="stat-row">
          <span>Deletions</span>
          <strong class="del">-{{ preview.stats.deletions }}</strong>
        </div>
      </div>
      <div v-if="preview.can_fast_forward" class="ff-note">Can fast-forward</div>
      <div v-if="preview.changed_files.length > 0" class="files">
        <strong>Changed files:</strong>
        <ul>
          <li v-for="f in preview.changed_files" :key="f">{{ f }}</li>
        </ul>
      </div>
    </div>
    <div v-if="error" class="error">{{ error }}</div>
    <template #footer>
      <Button severity="secondary" @click="emit('close')">
        <span>Cancel</span>
      </Button>
      <Button
        :disabled="!preview"
        @click="confirmMerge"
      >
        <Check :size="14" />
        <span>Merge</span>
      </Button>
    </template>
  </Dialog>
</template>

<style scoped>
.loading {
  padding: 16px;
  text-align: center;
  color: var(--p-text-muted-color);
}

.preview {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.branch-block {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.branch-label {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--p-text-muted-color);
}

.branch-name {
  font-size: 13px;
  padding: 6px 8px;
  background: var(--p-content-hover-background);
  border-radius: 4px;
  word-break: break-all;
}

.stats-grid {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.stat-row {
  display: flex;
  justify-content: space-between;
  font-size: 14px;
  padding: 5px 0;
  border-bottom: 1px solid var(--p-content-border-color);
}

.stat-row:last-child {
  border-bottom: none;
}

.ins {
  color: var(--p-green-600);
}
.del {
  color: var(--p-red-600);
}

.ff-note {
  color: var(--p-green-600);
  font-size: 14px;
}

.files {
  font-size: 14px;
}

.files ul {
  margin: 4px 0 0;
  padding-left: 20px;
}

.files li {
  color: var(--p-text-muted-color);
}

.error {
  color: var(--p-red-500);
  font-size: 14px;
  margin-top: 8px;
}
</style>
