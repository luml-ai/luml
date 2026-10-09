<template>
  <div class="details">
    <div class="details__part">
      <div class="details__item">
        <div class="details__label">Artifact ID</div>
        <div class="details__value">{{ artifact.id }}</div>
      </div>
      <div class="details__item">
        <div class="details__label">Artifact name</div>
        <div class="details__value">{{ artifact.name }}</div>
      </div>
      <div class="details__item">
        <div class="details__label">Status</div>
        <div class="details__value">
          <Tag
            v-if="statusConfig"
            :severity="statusConfig.severity"
            :value="statusConfig.text"
            class="tag"
          ></Tag>
        </div>
      </div>
      <div class="details__item">
        <div class="details__label">Creation time</div>
        <div class="details__value">{{ new Date(artifact.created_at).toLocaleString() }}</div>
      </div>
      <div class="details__item">
        <div class="details__label">Description</div>
        <div class="details__value">{{ artifact.description || '-' }}</div>
      </div>
      <div class="details__item">
        <div class="details__label">Tags</div>
        <div class="details__value">
          <div class="details__tags">
            <template v-if="artifact.tags?.length">
              <Tag v-for="tag in artifact.tags" :key="tag" :value="tag" class="tag"></Tag>
            </template>
            <span v-else>-</span>
          </div>
        </div>
      </div>
      <div class="details__item">
        <div class="details__label">Deployments</div>
        <div class="details__value">
          <div v-if="artifact.deployments?.length">
            <span v-for="(deployment, index) in artifact.deployments" :key="deployment.id">
              <RouterLink
                :to="deploymentRoute(deployment.id)"
                target="_blank"
                rel="noopener noreferrer"
                class="link"
              >
                {{ deployment.name }}
              </RouterLink>
              <span v-if="index < artifact.deployments.length - 1">, </span>
            </span>
          </div>
          <span v-else>-</span>
        </div>
      </div>
      <div class="details__item">
        <div class="details__label">Collection</div>
        <div class="details__value">
          <RouterLink v-if="collectionName" :to="collectionRoute" class="link">
            {{ collectionName }}
          </RouterLink>
          <span v-else>-</span>
        </div>
      </div>
      <div
        v-if="withManifest && artifact.manifest"
        class="details__item"
        style="align-items: center"
      >
        <div class="details__label">Manifest</div>
        <div class="details__value">
          <Button
            variant="text"
            size="small"
            severity="secondary"
            class="manifest-button"
            @click="manifestVisible = true"
          >
            Show
          </Button>
        </div>
      </div>
    </div>
    <div class="details__part">
      <div class="details__item">
        <div class="details__label">Size</div>
        <div class="details__value">{{ getSizeText(artifact.size) }}</div>
      </div>
      <div v-for="[metric, value] in metrics" :key="metric" class="details__item">
        <div class="details__label">{{ metric }}</div>
        <div class="details__value">{{ value }}</div>
      </div>
      <ArtifactTracks :tracks="artifact.tracks ?? []" />
    </div>
  </div>
  <ModelManifestModal
    v-if="withManifest && artifact.manifest"
    v-model:visible="manifestVisible"
    :manifest="artifact.manifest"
  ></ModelManifestModal>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, type RouteLocationRaw } from 'vue-router'
import { Button, Tag } from 'primevue'
import type { Artifact } from '@/lib/api/artifacts/interfaces'
import { getSizeText } from '@/helpers/helpers'
import { STATUS_TAGS_CONFIG } from '../artifacts-table/models-table.data'
import ModelManifestModal from '@/components/model/ModelManifestModal.vue'
import ArtifactTracks from '@/components/tracks/ArtifactTracks.vue'

interface Props {
  artifact: Artifact
  /** Adds the "Manifest: Show" row; the details panel of the design has none. */
  withManifest?: boolean
}

const props = withDefaults(defineProps<Props>(), { withManifest: false })
const route = useRoute()

const manifestVisible = ref(false)

const statusConfig = computed(() => STATUS_TAGS_CONFIG[props.artifact.status] ?? null)

const metrics = computed(() => Object.entries(props.artifact.extra_values ?? {}))

// The orbit listing carries `collection_name`, the artifact details carry `collection`.
const collectionName = computed(
  () => props.artifact.collection_name ?? props.artifact.collection?.name ?? null,
)

const collectionRoute = computed<RouteLocationRaw>(() => ({
  name: 'collection',
  params: {
    organizationId: route.params.organizationId,
    id: route.params.id,
    collectionId: props.artifact.collection_id,
  },
}))

function deploymentRoute(deploymentId: string): RouteLocationRaw {
  return {
    name: 'orbit-deployments',
    params: {
      organizationId: route.params.organizationId,
      id: route.params.id,
    },
    query: { deployment: deploymentId },
  }
}
</script>

<style scoped>
.details {
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
.details__value {
  overflow-wrap: anywhere;
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
.link {
  color: var(--p-primary-color);
  text-decoration: underline;
  transition: color 0.3s;
}
.link:hover {
  color: var(--p-text-link-hover-color);
}
.manifest-button {
  margin-left: -10px;
}
</style>
