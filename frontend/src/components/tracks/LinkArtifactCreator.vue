<template>
  <Dialog
    :visible="artifactLinksStore.creatorVisible"
    header="Link a new ARTIFACT"
    modal
    :draggable="false"
    :pt="DIALOG_PT"
    @update:visible="onVisibleChange"
  >
    <Form id="link-artifact-form" :initial-values="initialValues">
      <div class="fields">
        <CollectionSelect
          v-if="orbitsStore.currentOrbit"
          v-model="initialValues.collection"
          :disabled="false"
          :organization-id="orbitsStore.currentOrbit.organization_id"
          :orbit-id="orbitsStore.currentOrbit.id"
        />
        <div class="field">
          <label for="artifact-search" class="label"> Artifact </label>
          <IconField class="artifact-search-field">
            <InputText v-model="artifactSearch" fluid placeholder="Search artifacts" />
            <InputIcon>
              <Search :size="12" />
            </InputIcon>
          </IconField>
        </div>
        <ArtifactsList
          :list="artifactsList"
          :selected-artifact="initialValues.artifact"
          :organization-id="organizationId"
          :orbit-id="orbitId"
          @add="selectArtifact"
          @lazy-load="onLazyLoad"
        />
      </div>
    </Form>
    <template #footer>
      <Button
        label="Link"
        fluid
        rounded
        type="submit"
        form="link-artifact-form"
        :loading="loading"
        :disabled="!initialValues.artifact"
        @click="onSubmit"
      />
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { Form } from '@primevue/forms'
import { Button, Dialog, IconField, InputIcon, InputText, useToast } from 'primevue'
import { computed, ref, watch } from 'vue'
import { useArtifactLinksStore } from '@/stores/artifact-links/artifact-links'
import { useOrbitsStore } from '@/stores/orbits'
import { Search } from 'lucide-vue-next'
import { useArtifactsList } from '@/hooks/useArtifactsList'
import { useRoute } from 'vue-router'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { getErrorMessage } from '@/helpers/helpers'
import { useDebounceFn } from '@vueuse/core'
import { useTracksStore } from '@/stores/tracks'
import CollectionSelect from '@/components/orbits/tabs/registry/CollectionSelect.vue'
import ArtifactsList from '@/components/orbits/tabs/registry/collection/artifact/ArtifactsList.vue'
import type { Track } from '@/lib/api/orbit-tracks/interfaces'

const DIALOG_PT = {
  root: {
    style: 'width: 100%; max-width: 500px; height: 737px;',
  },
  header: {
    style: 'padding: 28px;',
  },
  title: {
    style: 'font-size: 20px; text-transform: uppercase;',
  },
  content: {
    style: 'padding: 0 28px;',
  },
  footer: {
    style: 'padding: 28px;',
  },
}

const toast = useToast()
const artifactLinksStore = useArtifactLinksStore()
const orbitsStore = useOrbitsStore()
const tracksStore = useTracksStore()
const route = useRoute()
const {
  setRequestInfo,
  getInitialPage,
  list: artifactsList,
  reset,
  onLazyLoad,
  setSearchQuery,
  setExcludedTracksQuery,
  setTypesQuery,
} = useArtifactsList(20, false)

const initialValues = ref({
  collection: '',
  artifact: '',
})
const artifactSearch = ref('')
const loading = ref(false)

const organizationId = computed(() => String(route.params.organizationId))
const orbitId = computed(() => String(route.params.id))
const trackId = computed(() => String(route.params.trackId) as string)

async function onSubmit() {
  if (!initialValues.value.artifact) return
  try {
    loading.value = true
    await artifactLinksStore.addEntry(trackId.value, {
      artifact_id: initialValues.value.artifact,
    })
    toast.add(simpleSuccessToast('Artifact linked to track'))
    artifactLinksStore.hideCreator()
  } catch (err: unknown) {
    toast.add(simpleErrorToast(getErrorMessage(err, 'Failed to link artifacts')))
  } finally {
    loading.value = false
  }
}

function onVisibleChange(value: boolean) {
  if (value) {
    artifactLinksStore.showCreator()
  } else {
    artifactLinksStore.hideCreator()
  }
}

function selectArtifact(id: string) {
  initialValues.value = { ...initialValues.value, artifact: id }
}

async function resetList() {
  try {
    await getInitialPage()
  } catch {
    toast.add(simpleErrorToast('Failed to reset list'))
  }
}

const debouncedOnSearch = useDebounceFn((query: string) => {
  setSearchQuery(query)
  resetList()
}, 500)

function onTrackChanged(track: Track | null) {
  if (track) {
    setTypesQuery([track.artifact_type])
    setExcludedTracksQuery([track.id])
  } else {
    setTypesQuery([])
    setExcludedTracksQuery([])
  }
}

function onVisibleChanged(value: boolean) {
  if (!value) return

  initialValues.value = {
    collection: '',
    artifact: '',
  }
  setRequestInfo({
    organizationId: organizationId.value,
    orbitId: orbitId.value,
    collectionIds: [],
  })
  resetList()
}

function onCollectionChanged(collectionId: string) {
  if (collectionId) {
    setRequestInfo({
      organizationId: organizationId.value,
      orbitId: orbitId.value,
      collectionIds: [collectionId],
    })
    resetList()
  } else {
    reset()
  }
}

watch(() => artifactLinksStore.creatorVisible, onVisibleChanged)

watch(() => initialValues.value.collection, onCollectionChanged)

watch(() => tracksStore.currentTrack, onTrackChanged, { immediate: true })

watch(artifactSearch, debouncedOnSearch)
</script>

<style scoped>
.fields {
  display: flex;
  flex-direction: column;
  gap: 8px;
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
