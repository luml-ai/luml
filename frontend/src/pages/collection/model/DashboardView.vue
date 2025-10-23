<template>
  <div v-if="currentModel" class="details">
    <div class="details__part">
      <div class="details__item">
        <div class="details__label">Model ID</div>
        <div class="details__value">{{ currentModel.id }}</div>
      </div>
      <div class="details__item">
        <div class="details__label">Model name</div>
        <div class="details__value">{{ currentModel.model_name }}</div>
      </div>
      <div class="details__item">
        <div class="details__label">Status</div>
        <div class="details__value">
          <Tag
            v-if="statusSeverity"
            :severity="statusSeverity"
            :value="currentModel.status"
            class="tag"
          ></Tag>
        </div>
      </div>
      <div class="details__item">
        <div class="details__label">Creation time</div>
        <div class="details__value">
          {{ new Date(currentModel.created_at).toLocaleString() }}
        </div>
      </div>
      <div class="details__item">
        <div class="details__label">Description</div>
        <div class="details__value">{{ currentModel.description || '-' }}</div>
      </div>
      <div class="details__item">
        <div class="details__label">Tags</div>
        <div class="details__value">
          <div class="details__tags">
            <Tag
              v-if="currentModel.tags?.length"
              v-for="tag in currentModel.tags"
              :value="tag"
              class="tag"
            ></Tag>
            <span v-else>-</span>
          </div>
        </div>
      </div>
      <div v-if="currentModel?.manifest" class="details__item" style="align-items: center">
        <div class="details__label">Manifest</div>
        <div class="details__value">
          <Button variant="text" size="small" severity="secondary" @click="showManifest">
            Show
          </Button>
        </div>
      </div>
    </div>
    <div class="details__part">
      <div class="details__item">
        <div class="details__label">Size</div>
        <div class="details__value">{{ getSizeText(currentModel.size) }}</div>
      </div>
      <div v-for="metric in Object.entries(currentModel.metrics)" class="details__item">
        <div class="details__label">{{ metric[0] }}</div>
        <div class="details__value">{{ metric[1] }}</div>
      </div>
    </div>
  </div>
  <ModelManifestModal
    v-if="currentModel?.manifest"
    v-model:visible="manifestVisible"
    :manifest="currentModel?.manifest"
  ></ModelManifestModal>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useModelsStore } from '@/stores/models'
import { useRoute } from 'vue-router'
import { Tag, Button } from 'primevue'
import { MlModelStatusEnum } from '@/lib/api/orbit-ml-models/interfaces'
import { getSizeText } from '@/helpers/helpers'
import { ref } from 'vue'
import ModelManifestModal from '@/components/model/ModelManifestModal.vue'

const modelsStore = useModelsStore()
const route = useRoute()

const manifestVisible = ref(false)

const currentModel = computed(() => {
  if (typeof route.params.modelId !== 'string') return undefined
  return modelsStore.modelsList.find((model) => model.id === route.params.modelId)
})
const statusSeverity = computed(() => {
  if (!currentModel.value) return null
  else if (
    [MlModelStatusEnum.deletion_failed, MlModelStatusEnum.upload_failed].includes(
      currentModel.value.status,
    )
  )
    return 'danger'
  else if (
    [MlModelStatusEnum.pending_deletion, MlModelStatusEnum.pending_upload].includes(
      currentModel.value.status,
    )
  )
    return 'warn'
  else if (currentModel.value.status === MlModelStatusEnum.uploaded) return 'success'
})

function showManifest() {
  manifestVisible.value = true
}
</script>

<style scoped>
.details {
  padding: 20px;
  background-color: var(--p-card-background);
  border-radius: 8px;
  border: 1px solid var(--p-content-border-color);
  box-shadow: var(--card-shadow);
  display: flex;
  flex-direction: column;
  gap: 28px;
}
.details__part {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.details__item {
  display: grid;
  align-items: flex-start;
  grid-template-columns: 100px 1fr;
  gap: 24px;
  font-size: 14px;
}
.details__label {
  color: var(--p-text-muted-color);
  line-height: 1.21;
  overflow: hidden;
  text-overflow: ellipsis;
}
.details__tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}
.tag {
  font-weight: 400;
  padding: 2px 4px;
}
</style>
