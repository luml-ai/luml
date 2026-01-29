<template>
  <div v-if="artifactsStore.currentArtifact" class="details">
    <div class="details__part">
      <div class="details__item">
        <div class="details__label">Model ID</div>
        <div class="details__value">{{ artifactsStore.currentArtifact.id }}</div>
      </div>
      <div class="details__item">
        <div class="details__label">Model name</div>
        <div class="details__value">{{ artifactsStore.currentArtifact.name }}</div>
      </div>
      <div class="details__item">
        <div class="details__label">Status</div>
        <div class="details__value">
          <Tag
            v-if="statusSeverity"
            :severity="statusSeverity"
            :value="artifactsStore.currentArtifact.status"
            class="tag"
          ></Tag>
        </div>
      </div>
      <div class="details__item">
        <div class="details__label">Creation time</div>
        <div class="details__value">
          {{ new Date(artifactsStore.currentArtifact.created_at).toLocaleString() }}
        </div>
      </div>
      <div class="details__item">
        <div class="details__label">Description</div>
        <div class="details__value">{{ artifactsStore.currentArtifact.description || '-' }}</div>
      </div>
      <div class="details__item">
        <div class="details__label">Tags</div>
        <div class="details__value">
          <div class="details__tags">
            <Tag
              v-if="artifactsStore.currentArtifact.tags?.length"
              v-for="tag in artifactsStore.currentArtifact.tags"
              :value="tag"
              class="tag"
            ></Tag>
            <span v-else>-</span>
          </div>
        </div>
      </div>
      <div
        v-if="artifactsStore.currentArtifact?.manifest"
        class="details__item"
        style="align-items: center"
      >
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
        <div class="details__value">{{ getSizeText(artifactsStore.currentArtifact.size) }}</div>
      </div>
      <div
        v-for="metric in Object.entries(artifactsStore.currentArtifact.extra_values)"
        class="details__item"
      >
        <div class="details__label">{{ metric[0] }}</div>
        <div class="details__value">{{ metric[1] }}</div>
      </div>
    </div>
  </div>
  <ModelManifestModal
    v-if="artifactsStore.currentArtifact?.manifest"
    v-model:visible="manifestVisible"
    :manifest="artifactsStore.currentArtifact.manifest"
  ></ModelManifestModal>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Tag, Button } from 'primevue'
import { ArtifactStatusEnum } from '@/lib/api/artifacts/interfaces'
import { getSizeText } from '@/helpers/helpers'
import { ref } from 'vue'
import { useArtifactsStore } from '@/stores/artifacts'
import ModelManifestModal from '@/components/model/ModelManifestModal.vue'

const artifactsStore = useArtifactsStore()

const manifestVisible = ref(false)

const statusSeverity = computed(() => {
  if (!artifactsStore.currentArtifact) return null
  else if (
    [ArtifactStatusEnum.deletion_failed, ArtifactStatusEnum.upload_failed].includes(
      artifactsStore.currentArtifact.status,
    )
  )
    return 'danger'
  else if (
    [ArtifactStatusEnum.pending_deletion, ArtifactStatusEnum.pending_upload].includes(
      artifactsStore.currentArtifact.status,
    )
  )
    return 'warn'
  else if (artifactsStore.currentArtifact.status === ArtifactStatusEnum.uploaded) return 'success'
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
