<template>
  <Button v-if="loading" :loading="loading" severity="secondary" variant="outlined" />
  <Button
    v-else-if="authStore.isAuthenticated"
    severity="secondary"
    variant="outlined"
    @click="openApiKeyModal"
  >
    <template #icon>
      <KeyRound :size="14" color="var(--p-button-outlined-plain-color)" />
    </template>
  </Button>
  <Button v-else @click="openApiKeyModal" severity="secondary" variant="outlined">
    <KeyRound :size="14" color="var(--p-button-outlined-plain-color)" />
    <span class="text-(--p-button-outlined-plain-color)">Connect to LUML</span>
  </Button>
</template>

<script setup lang="ts">
import { KeyRound } from 'lucide-vue-next'
import { Button } from 'primevue'
import { useAuthStore } from '@/store/auth'
import { onBeforeMount, ref } from 'vue'

const loading = ref(true)

const authStore = useAuthStore()

function openApiKeyModal() {
  authStore.showApiKeyModal()
}

onBeforeMount(async () => {
  try {
    await authStore.checkAuth()
  } catch (error) {
    console.error(error)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped></style>
