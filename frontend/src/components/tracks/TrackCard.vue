<template>
  <UiRichCard
    :title="props.name"
    :id="props.id"
    :editAvailable="editAvailable"
    :createdAt="props.createdAt"
    :updatedAt="props.updatedAt"
    :type="formattedType"
    :totalArtifacts="props.artifactsCount"
    :description="props.description ?? ''"
    :tags="props.tags"
    :to="to"
    @edit-click="showEditor"
  />
</template>

<script setup lang="ts">
import type { TrackCardProps } from './tracks.interface'
import { useOrbitsStore } from '@/stores/orbits'
import { PermissionEnum } from '@/lib/api/api.interfaces'
import { computed } from 'vue'
import { useTracksStore } from '@/stores/tracks'
import UiRichCard from '@/components/ui/UiRichCard.vue'
import type { OrbitCollectionTypeEnum } from '@/lib/api/orbit-collections/interfaces'

const props = defineProps<TrackCardProps>()

const tracksStore = useTracksStore()
const orbitsStore = useOrbitsStore()
const editAvailable = computed(
  () => !!orbitsStore.getCurrentOrbitPermissions?.track?.includes(PermissionEnum.update),
)

const formattedType = computed(() => {
  return props.type as unknown as OrbitCollectionTypeEnum
})

const to = computed(() => {
  return {
    name: 'track',
    params: {
      trackId: props.id,
    },
  }
})

function showEditor() {
  if (!editAvailable.value) return
  tracksStore.showEditor({
    id: props.id,
    name: props.name,
    description: props.description,
    stages: props.stages,
  })
}
</script>
