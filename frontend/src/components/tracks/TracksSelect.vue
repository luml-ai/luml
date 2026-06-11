<template>
  <div class="field">
    <label :for="controlId" class="label" :class="{ required: required }">Track</label>
    <Select
      v-model="modelValue"
      :id="controlId"
      :name="name"
      placeholder="Select track"
      fluid
      option-label="name"
      option-value="id"
      :options="filteredTracksList"
      :disabled="disabled"
      :virtualScrollerOptions="virtualScrollerOptions"
      :loading="isLoading"
      :pt="{
        overlay: 'tracks-select-overlay',
      }"
    >
      <template #header>
        <div class="search-wrapper">
          <IconField>
            <InputText v-model="search" placeholder="Search tracks" size="small" fluid />
            <InputIcon>
              <Search :size="12" />
            </InputIcon>
          </IconField>
        </div>
      </template>
      <template #option="{ option }">
        <TrackCardSmall :data="option" />
      </template>
    </Select>
  </div>
</template>

<script setup lang="ts">
import { IconField, InputIcon, InputText, Select, useToast } from 'primevue'
import { getErrorMessage } from '@/helpers/helpers'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { computed, ref, watch } from 'vue'
import { useTracksList } from '@/hooks/useTracksList'
import { Search } from 'lucide-vue-next'
import { useDebounceFn } from '@vueuse/core'
import TrackCardSmall from './TrackCardSmall.vue'
import type { ArtifactTypeEnum } from '@/lib/api/artifacts/interfaces.js'

type Props = {
  controlId?: string
  required?: boolean
  name?: string
  disabled: boolean
  organizationId: string
  orbitId: string
  types?: ArtifactTypeEnum[]
  hiddenTracks?: string[]
}

const props = withDefaults(defineProps<Props>(), {
  controlId: 'track',
  required: false,
  name: 'track',
  hiddenTracks: () => [],
})

const toast = useToast()
const {
  tracksList,
  setRequestInfo,
  getInitialPage,
  reset,
  onLazyLoad,
  isLoading,
  setSearchQuery,
  searchQuery,
  setTypesQuery,
} = useTracksList()

const search = ref(searchQuery.value)

const filteredTracksList = computed(() => {
  return tracksList.value.filter((track) => !props.hiddenTracks.includes(track.id))
})

const virtualScrollerOptions = computed(() => {
  if (tracksList.value.length < 10) return undefined
  return { lazy: true, onLazyLoad: onLazyLoad, itemSize: 107 }
})

const modelValue = defineModel<string | null>()

async function refreshList() {
  try {
    reset()
    setRequestInfo({
      organizationId: props.organizationId,
      orbitId: props.orbitId,
    })
    await getInitialPage()
  } catch (e) {
    const message = getErrorMessage(e, 'Failed to load tracks')
    toast.add(simpleErrorToast(message))
  }
}

async function onRequestInfoChange() {
  if (props.types) {
    setTypesQuery(props.types)
  }
  refreshList()
}

const debouncedSetSearchQuery = useDebounceFn((query: string) => {
  setSearchQuery(query)
  refreshList()
}, 500)

watch(search, (value) => {
  debouncedSetSearchQuery(value)
})

watch(() => [props.organizationId, props.orbitId], onRequestInfoChange, {
  immediate: true,
  deep: true,
})
</script>

<style scoped>
.field {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.dropdown-title {
  padding: 12px 16px 8px;
  font-size: 14px;
  font-weight: var(--p-select-option-group-font-weight);
  color: var(--p-select-option-group-color);
}

.search-wrapper {
  padding: 4px 4px 8px;
}

:deep(.p-iconfield .p-inputicon:last-child) {
  inset-inline-end: 12px;
}
</style>

<style>
.tracks-select-overlay .p-select-option {
  padding: 0;
  background-color: transparent !important;
}
</style>
