<template>
  <section class="welcome">
    <div class="texts">
      <h1 class="title">The agent-native MLOps platform</h1>
      <p class="subtitle">
        Work alongside AI agents on ML projects: run experiments, version, deploy, and monitor
        models in one place.
      </p>
    </div>
    <router-link v-if="!authStore.isAuth" :to="{ name: 'sign-up' }" custom v-slot="{ navigate }">
      <d-button label="Get started free" @click="navigate" />
    </router-link>
    <d-button
      v-else-if="showQuickStart"
      label="Check out Quick start"
      severity="secondary"
      @click="emit('quick-start')"
    >
      <span>Check out Quick start</span>
      <Sparkles :size="14" />
    </d-button>
  </section>
</template>

<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'
import { Sparkles } from 'lucide-vue-next'

defineProps<{ showQuickStart: boolean }>()

const emit = defineEmits<{ 'quick-start': [] }>()

const authStore = useAuthStore()
</script>

<style scoped>
.welcome {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 24px;
}

.texts {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.title {
  font-size: 40px;
  font-weight: 500;
  letter-spacing: -0.8px;
  line-height: normal;
  color: var(--p-text-color);
}

.subtitle {
  font-size: 16px;
  line-height: 24px;
  color: var(--p-text-color);
}

@media (max-width: 768px) {
  .title {
    font-size: 32px;
  }
}
</style>
