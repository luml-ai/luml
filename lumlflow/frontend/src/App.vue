<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from './api/client'

const message = ref('')
const loading = ref(true)

onMounted(async () => {
  try {
    const response = await api.get('/api/hello')
    message.value = response.data.message
  } catch (e) {
    message.value = 'Failed to connect to API'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="app">
    <h1>Lumlflow</h1>
    <p v-if="loading">Loading...</p>
    <p v-else>{{ message }}</p>
  </div>
</template>

<style scoped>
.app {
  max-width: 800px;
  margin: 2rem auto;
  padding: 1rem;
}
</style>
