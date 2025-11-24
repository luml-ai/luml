<template>
  <div class="navigation">
    <d-button severity="secondary" @click="onBackClick">
      <arrow-left :size="14" />
      <span>Back</span>
    </d-button>
    <d-button severity="secondary" @click="onFinishClick">
      <span>exit</span>
      <log-out width="14" height="14" />
    </d-button>
  </div>
</template>

<script setup lang="ts">
import { AnalyticsService, AnalyticsTrackKeysEnum } from '@/lib/analytics/AnalyticsService'
import { ArrowLeft, LogOut } from 'lucide-vue-next'
import { useRoute, useRouter } from 'vue-router'

type Emits = {
  goBack: []
}

const emit = defineEmits<Emits>()

const route = useRoute()
const router = useRouter()

function onBackClick() {
  if (route.params.mode === 'data-driven') {
    emit('goBack')
  } else {
    router.back()
  }
}
function onFinishClick() {
  AnalyticsService.track(AnalyticsTrackKeysEnum.finish, { task: 'prompt_optimization' })
  router.push({ name: 'home' })
}
</script>

<style scoped>
.navigation {
  position: absolute;
  left: 16px;
  bottom: -15px;
  display: flex;
  gap: 16px;
  z-index: 2;
}
</style>
