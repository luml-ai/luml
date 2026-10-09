<template>
  <UiRichCard
    :title="data.name"
    :id="data.id"
    :editAvailable="editAvailable"
    :createdAt="data.created_at"
    :updatedAt="data.updated_at"
    :type="data.type"
    :totalArtifacts="data.total_artifacts"
    :description="data.description"
    :tags="data.tags ?? []"
    :to="to"
    @edit-click="showEditor"
  />
  <CollectionEditor v-model:visible="isEditorVisible" :data="data"></CollectionEditor>
</template>

<script setup lang="ts">
import { type OrbitCollection } from '@/lib/api/orbit-collections/interfaces'
import { computed, ref } from 'vue'
import CollectionEditor from './CollectionEditor.vue'
import UiRichCard from '@/components/ui/UiRichCard.vue'

type Props = {
  data: OrbitCollection
  editAvailable: boolean
}

const props = defineProps<Props>()

const isEditorVisible = ref(false)

const to = computed(() => {
  return {
    name: 'collection',
    params: {
      id: props.data.orbit_id,
      collectionId: props.data.id,
    },
  }
})

function showEditor() {
  isEditorVisible.value = true
}
</script>
