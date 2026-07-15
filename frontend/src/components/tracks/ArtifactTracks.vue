<template>
  <div v-if="tracks.length" class="row">
    <div class="label">Tracks</div>
    <div class="value">
      <template v-for="(track, index) in tracks" :key="track.id">
        <a
          :href="`/organization/${organizationId}/orbit/${orbitId}/tracks/${track.id}`"
          target="_blank"
          rel="noopener noreferrer"
          class="link"
        >
          {{ track.name }}
        </a>
        <span v-if="index !== tracks.length - 1">, </span>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import type { ArtifactTrack } from '@/lib/api/artifacts/interfaces'

interface Props {
  tracks: ArtifactTrack[]
}

defineProps<Props>()

const route = useRoute()

const organizationId = computed(() => String(route.params.organizationId))
const orbitId = computed(() => String(route.params.id))
</script>

<style scoped>
.row {
  display: grid;
  align-items: flex-start;
  grid-template-columns: 100px 1fr;
  gap: 24px;
  font-size: 14px;
}
.label {
  color: var(--p-text-muted-color);
  line-height: 1.21;
  overflow: hidden;
  text-overflow: ellipsis;
}
.link {
  text-decoration: underline;
  transition: color 0.3s;
}
.link:hover {
  color: var(--p-text-link-hover-color);
}
</style>
