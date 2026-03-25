<template>
  <div class="empty-state">
    <div class="grid">
      <div class="card card--action">
        <template v-if="!authStore.isAuth">
          <div class="content">
            <div class="title">Get Started</div>
            <p class="text">Log in or create an account to start using this feature.</p>
          </div>
          <div class="actions">
            <d-button
              label="Log in"
              severity="secondary"
              @click="$router.push({ name: 'sign-in' })"
            />
            <d-button label="Sign up" @click="$router.push({ name: 'sign-up' })" />
          </div>
        </template>
        <template v-else>
          <div class="content">
            <div class="title">Create an Orbit</div>
            <p class="text">
              Create your first orbit to start organizing models, deployments and satellites.
            </p>
          </div>
          <div class="actions">
            <d-button label="Create orbit" @click="onCreateOrbit"> </d-button>
          </div>
        </template>
      </div>
      <div v-for="card in cards" :key="card.title" class="card">
        <div class="content">
          <div class="title">{{ card.title }}</div>
          <p class="text">{{ card.description }}</p>
        </div>
      </div>
    </div>
    <OrbitCreator
      v-if="organizationStore.currentOrganization"
      v-model:visible="isCreateMode"
      :organization-id="organizationStore.currentOrganization.id"
    />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Orbit, Plus } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import { useOrganizationStore } from '@/stores/organization'
import OrbitCreator from '@/components/orbits/creator/OrbitCreator.vue'

type EmptyStateCard = {
  title: string
  description: string
}

defineProps<{ cards: EmptyStateCard[] }>()

const authStore = useAuthStore()
const organizationStore = useOrganizationStore()
const isCreateMode = ref(false)

function onCreateOrbit() {
  isCreateMode.value = true
}
</script>

<style scoped>
.grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
  padding-top: 37px;
}

.card {
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  box-shadow: var(--card-shadow);
  border-radius: 8px;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.title {
  font-size: 20px;
  font-weight: 500;
  line-height: 24px;
  margin-bottom: 8px;
  color: var(--p-text-color);
}

.text {
  color: var(--p-text-muted-color);
  font-size: 14px;
  font-weight: 400;
  line-height: 20px;
}

.actions {
  display: flex;
  gap: 12px;
  margin-top: auto;
}

.actions .p-button {
  flex: 1;
}
@media (max-width: 992px) {
  .grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 576px) {
  .grid {
    grid-template-columns: 1fr;
  }
}
</style>
