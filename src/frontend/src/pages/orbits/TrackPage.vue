<template>
  <UiPageLoader v-if="loading"></UiPageLoader>
  <div v-else-if="tracksStore.currentTrack" class="view">
    <TrackBreadCrumbs
      :track-name="tracksStore.currentTrack.name"
      :track-id="tracksStore.currentTrack.id"
      class="breadcrumbs"
    />
    <div class="header">
      <h1 class="title">{{ tracksStore.currentTrack.name }}</h1>
      <Button
        label="Link artifact"
        class="link-artifact-btn"
        @click="artifactLinksStore.showCreator"
      >
        <template #icon>
          <Plus :size="14" />
        </template>
      </Button>
    </div>
    <LinksWrapper />
    <LinkArtifactCreator />
  </div>
  <Ui404 v-else></Ui404>
</template>

<script setup lang="ts">
import { Plus } from 'lucide-vue-next'
import { Button, useToast } from 'primevue'
import { useArtifactLinksStore } from '@/stores/artifact-links/artifact-links'
import { useTracksStore } from '@/stores/tracks'
import { useRoute } from 'vue-router'
import { onBeforeMount, ref } from 'vue'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import TrackBreadCrumbs from '@/components/tracks/TrackBreadcrumbs.vue'
import LinkArtifactCreator from '@/components/tracks/LinkArtifactCreator.vue'
import UiPageLoader from '@/components/ui/UiPageLoader.vue'
import Ui404 from '@/components/ui/Ui404.vue'
import LinksWrapper from '@/components/tracks/LinksWrapper.vue'

const artifactLinksStore = useArtifactLinksStore()
const tracksStore = useTracksStore()
const route = useRoute()
const toast = useToast()

const loading = ref(true)

async function init() {
  try {
    loading.value = true
    const trackId = String(route.params.trackId)
    await tracksStore.setCurrentTrack(trackId)
  } catch {
    toast.add(simpleErrorToast('Failed to load track data'))
  } finally {
    loading.value = false
  }
}

onBeforeMount(init)
</script>

<style scoped>
.view {
  padding-top: 18px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.title {
  white-space: nowrap;
  flex: 1 1 auto;
  overflow: hidden;
  text-overflow: ellipsis;
}

.link-artifact-btn {
  flex: 0 0 auto;
}
</style>
