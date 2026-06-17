<template>
  <div class="page-header">
    <div class="page-header__left">
      <Folders :size="20" class="page-header__icon" />
      <h1 class="page-header__title">Registry</h1>
    </div>
    <template v-if="authStore.isAuth">
      <d-button :label="buttonProps.label" @click="buttonProps.action">
        <template #icon>
          <Plus :size="14" />
        </template>
      </d-button>
    </template>
  </div>
</template>

<script setup lang="ts">
import { Folders, Plus } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import { useCollectionsStore } from '@/stores/collections'
import { useTracksStore } from '@/stores/tracks'
import { useRoute } from 'vue-router'
import { computed } from 'vue'

const authStore = useAuthStore()
const collectionsStore = useCollectionsStore()
const tracksStore = useTracksStore()
const route = useRoute()

const buttonProps = computed(() => {
  return route.name === 'orbit-tracks'
    ? { label: 'Create track', action: tracksStore.showCreator }
    : { label: 'Create collection', action: collectionsStore.showCreator }
})
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 25px;
  padding-top: 37px;
}

.page-header__left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.page-header__icon {
  width: 20px;
  height: 20px;
  color: var(--p-primary-color);
}

.page-header__title {
  font-weight: 500;
  line-height: 30px;
  letter-spacing: -0.48px;
}
</style>
