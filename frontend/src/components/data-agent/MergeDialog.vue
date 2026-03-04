<script setup lang="ts">
import { ref, watch } from 'vue'
import { Dialog, Button } from 'primevue'
import { Check } from 'lucide-vue-next'
import type { AgentTask, MergePreview } from '@/lib/api/data-agent/data-agent.interfaces'
import { api } from '@/lib/api'

const props = defineProps<{
  visible: boolean
  task: AgentTask
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
        preview.value = await api.dataAgent.getMergePreview(props.task.id)
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
    await api.dataAgent.mergeTask(props.task.id)
    emit('merged')
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Merge failed'
  }
}
</script>

<template>
  <Dialog
    :visible="visible"
    header="Merge Branch"
    modal
    :style="{ width: '500px' }"
    @update:visible="!$event && emit('close')"
  >
    <div v-if="loading" class="loading">Loading preview...</div>
    <div v-else-if="preview" class="preview">
      <div class="stat-row">
        <span>Branch:</span>
        <strong>{{ preview.branch }}</strong>
      </div>
      <div class="stat-row">
        <span>Into:</span>
        <strong>{{ preview.base_branch }}</strong>
      </div>
      <div class="stat-row">
        <span>Commits:</span>
        <strong>{{ preview.stats.commits_ahead }}</strong>
      </div>
      <div class="stat-row">
        <span>Files changed:</span>
        <strong>{{ preview.stats.files_changed }}</strong>
      </div>
      <div class="stat-row">
        <span>Insertions:</span>
        <strong class="ins">+{{ preview.stats.insertions }}</strong>
      </div>
      <div class="stat-row">
        <span>Deletions:</span>
        <strong class="del">-{{ preview.stats.deletions }}</strong>
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
  gap: 6px;
}

.stat-row {
  display: flex;
  justify-content: space-between;
  font-size: 14px;
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
  margin-top: 4px;
}

.files {
  margin-top: 8px;
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
