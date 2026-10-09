<template>
  <UiDialogRight v-model:visible="visible" :icon="Info" title="Artifact details" max-width="581px">
    <template v-if="data">
      <div v-if="data.isDeleted" class="deleted">
        <div class="deleted__heading">
          <Tag :severity="typeConfig.severity" class="deleted__type">
            <component :is="typeConfig.icon" :size="14" />
            {{ typeConfig.text }}
          </Tag>
          <h3 class="deleted__name">{{ data.title }}</h3>
        </div>
        <dl class="deleted__properties">
          <div class="deleted__property">
            <dt>Collection</dt>
            <dd>{{ data.collectionName ?? 'Unknown collection' }}</dd>
          </div>
          <div class="deleted__property">
            <dt>Status</dt>
            <dd><Tag severity="danger">Deleted</Tag></dd>
          </div>
        </dl>
      </div>
      <ArtifactDetails v-else-if="artifact" :artifact="artifact" />
      <div v-else class="loader">
        <ProgressSpinner style="width: 40px; height: 40px" />
      </div>
    </template>

    <template #footer>
      <div v-if="artifactRoute" class="actions">
        <RouterLink :to="artifactRoute" class="actions__link">
          <ExternalLink :size="14" />
          Open artifact
        </RouterLink>
        <RouterLink
          v-if="data?.variant !== 'main' && lineageRoute"
          :to="lineageRoute"
          class="actions__link"
        >
          <Workflow :size="14" />
          Focus lineage
        </RouterLink>
      </div>
    </template>
  </UiDialogRight>
</template>

<script setup lang="ts">
import type { LineageNodeData } from './lineage.interface'
import type { Artifact } from '@/lib/api/artifacts/interfaces'
import { api } from '@/lib/api'
import { getErrorMessage } from '@/helpers/helpers'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { ARTIFACT_TYPE_TAGS_CONFIG } from '@/components/orbits/tabs/registry/collection/artifacts-table/models-table.data'
import ArtifactDetails from '@/components/orbits/tabs/registry/collection/artifact/ArtifactDetails.vue'
import UiDialogRight from '@/components/ui/dialogs/UiDialogRight.vue'
import { ExternalLink, Info, Workflow } from 'lucide-vue-next'
import { ProgressSpinner, Tag, useToast } from 'primevue'
import { computed, ref, watch } from 'vue'
import { useRoute, type RouteLocationRaw } from 'vue-router'

interface Props {
  data: LineageNodeData | null
}

const props = defineProps<Props>()
const visible = defineModel<boolean>('visible', { default: false })
const route = useRoute()
const toast = useToast()

// The graph carries the orbit listing of every live node; the artifact
// details (tracks, full deployments) are fetched when the panel opens.
const details = ref<Artifact | null>(null)
let requestId = 0

const artifact = computed<Artifact | null>(() => {
  if (!props.data || props.data.isDeleted) return null
  return details.value ?? props.data.data
})

const typeConfig = computed(() => {
  if (!props.data) throw new Error('Artifact details are not available')
  return ARTIFACT_TYPE_TAGS_CONFIG[props.data.type]
})

function artifactLocation(name: 'artifact' | 'lineage'): RouteLocationRaw | null {
  if (!props.data?.artifactId || !props.data.collectionId) return null
  return {
    name,
    params: {
      organizationId: route.params.organizationId,
      id: route.params.id,
      collectionId: props.data.collectionId,
      artifactId: props.data.artifactId,
    },
  }
}

const artifactRoute = computed(() => artifactLocation('artifact'))
const lineageRoute = computed(() => artifactLocation('lineage'))

async function loadDetails(data: LineageNodeData): Promise<void> {
  if (data.isDeleted || !data.artifactId || !data.collectionId) return
  const id = ++requestId
  try {
    const loaded = await api.artifacts.getById(
      String(route.params.organizationId),
      String(route.params.id),
      data.collectionId,
      data.artifactId,
    )
    if (id === requestId) details.value = loaded
  } catch (error) {
    if (id !== requestId) return
    toast.add(simpleErrorToast(getErrorMessage(error, 'Failed to load artifact details')))
  }
}

watch(
  () => props.data,
  (data) => {
    details.value = null
    requestId += 1
    if (data) void loadDetails(data)
  },
  { immediate: true },
)
</script>

<style scoped>
.deleted {
  display: flex;
  flex-direction: column;
  gap: 24px;
}
.deleted__heading {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 10px;
}
.deleted__type {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.deleted__name {
  margin: 0;
  font-size: 20px;
  font-weight: 500;
  overflow-wrap: anywhere;
}
.deleted__properties {
  margin: 0;
}
.deleted__property {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 10px 0;
  border-bottom: 1px solid var(--p-content-border-color);
  font-size: 14px;
}
.deleted__property dt {
  color: var(--p-text-muted-color);
}
.deleted__property dd {
  margin: 0;
  text-align: right;
}
.loader {
  display: flex;
  justify-content: center;
  padding: 40px 0;
}
.actions {
  display: flex;
  width: 100%;
  justify-content: flex-end;
  gap: 12px;
}
.actions__link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 8px 14px;
  border: 1px solid var(--p-button-secondary-border-color);
  border-radius: var(--p-button-border-radius);
  color: var(--p-button-secondary-color);
  background: var(--p-button-secondary-background);
  text-decoration: none;
  font-size: 14px;
}
.actions__link:hover {
  background: var(--p-button-secondary-hover-background);
}
</style>
