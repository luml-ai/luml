<template>
  <UiRichCard
    :title="props.name"
    :id="props.id"
    :editAvailable="true"
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
import { computed } from 'vue'
import { useTracksStore } from '@/stores/tracks'
import UiRichCard from '@/components/ui/UiRichCard.vue'
import type { OrbitCollectionTypeEnum } from '@/lib/api/orbit-collections/interfaces'

const props = defineProps<TrackCardProps>()

const tracksStore = useTracksStore()

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
  tracksStore.showEditor({
    id: props.id,
    name: props.name,
    description: props.description,
    stages: props.stages,
  })
}
</script>
