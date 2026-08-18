<template>
  <div>
    <div class="fields">
      <CollectionSelect
        v-model="values.collection"
        :disabled="false"
        :organization-id="organizationId"
        :orbit-id="orbitId"
      />

      <div class="field">
        <label for="type" class="label"> Type </label>
        <Select
          v-model="values.type"
          :options="ARTIFACT_TYPE_OPTIONS"
          option-label="label"
          option-value="value"
          placeholder="Select type"
          name="type"
          id="type"
          fluid
          label-id="type"
        />
      </div>
      <div class="field">
        <label for="artifact-search" class="label"> Artifact </label>
        <IconField class="artifact-search-field">
          <InputText
            v-model="values.search"
            fluid
            placeholder="Search artifacts"
            name="artifactSearch"
            id="artifact-search"
          />
          <InputIcon>
            <Search :size="12" />
          </InputIcon>
        </IconField>
      </div>
    </div>
    <ArtifactsList
      :list="filteredList"
      :selected-artifact="selectedArtifact?.id ?? null"
      :organization-id="organizationId"
      :orbit-id="orbitId"
      height="310px"
      @add="selectArtifact"
      @lazy-load="onLazyLoad"
    />
  </div>
</template>

<script setup lang="ts">
import type { AxiosError } from 'axios'
import type { Artifact, ArtifactTypeEnum } from '@/lib/api/artifacts/interfaces'
import { IconField, InputIcon, InputText, Select, useToast } from 'primevue'
import { Search } from 'lucide-vue-next'
import { computed, onBeforeMount, ref, watch } from 'vue'
import { ARTIFACT_TYPE_OPTIONS } from '../orbits/tabs/registry/collection/artifacts-table/models-table.data'
import { useArtifactsList } from '@/hooks/useArtifactsList'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import CollectionSelect from '../orbits/tabs/registry/CollectionSelect.vue'
import ArtifactsList from '../orbits/tabs/registry/collection/artifact/ArtifactsList.vue'

interface Props {
  organizationId: string
  orbitId: string
  lockedArtifacts: string[]
}

const props = defineProps<Props>()

const toast = useToast()
const {
  requestInfo,
  setRequestInfo,
  getInitialPage,
  onLazyLoad,
  setSearchQuery,
  setTypesQuery,
  filteredList,
} = useArtifactsList(
  20,
  false,
  undefined,
  computed(() => props.lockedArtifacts),
)

const values = ref({
  collection: null,
  type: null,
  search: null,
})
const selectedArtifact = defineModel<Artifact | null>('artifact', { default: null })
const isResetting = ref(false)

function selectArtifact(artifactId: string) {
  const artifact = filteredList.value.find((a) => a.id === artifactId)
  if (!artifact) return
  selectedArtifact.value = artifact
}
function clearSelectedArtifact() {
  selectedArtifact.value = null
}

async function loadFirstPage() {
  if (!requestInfo.value) return
  try {
    await getInitialPage()
  } catch (e: unknown) {
    const error = e as AxiosError
    if (error.code === 'ERR_CANCELED') return
    toast.add(simpleErrorToast('Failed to reset list'))
  }
}

function onCollectionChanged(collectionId: string | null) {
  setRequestInfo({
    organizationId: props.organizationId,
    orbitId: props.orbitId,
    collectionIds: collectionId ? [collectionId] : [],
  })
  clearSelectedArtifact()
  loadFirstPage()
}

function onTypeChanged(type: ArtifactTypeEnum | null) {
  clearSelectedArtifact()
  setTypesQuery(type ? [type] : [])
}

watch(
  () => values.value.collection,
  (collectionId: string | null) => {
    if (isResetting.value) return
    onCollectionChanged(collectionId)
  },
)

watch(
  () => values.value.type,
  (type: ArtifactTypeEnum | null) => {
    if (isResetting.value) return
    onTypeChanged(type)
  },
)

watch(
  () => values.value.search,
  (query: string | null) => {
    if (isResetting.value) return
    clearSelectedArtifact()
    setSearchQuery(query ?? '')
  },
)

onBeforeMount(() => {
  setRequestInfo({
    organizationId: props.organizationId,
    orbitId: props.orbitId,
    collectionIds: [],
  })
  loadFirstPage()
})
</script>

<style scoped>
.fields {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 14px;
}
.field {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 7px;
}
.artifact-search-field {
  width: 100%;
}
:deep(.p-iconfield .p-inputicon:last-child) {
  inset-inline-end: 14px;
}
</style>
