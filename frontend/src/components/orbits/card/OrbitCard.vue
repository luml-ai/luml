<template>
  <article class="card" :class="{ 'card--clickable': type === 'default' }">
    <div
      v-if="type === 'default' && data"
      class="content content--clickable"
      @click="$router.push({ name: 'orbit-registry', params: { id: data.id } })"
    >
      <div class="header">
        <h3 class="title">
          <Orbit :size="24" color="var(--p-primary-color)" class="icon" />
          <span>{{ data.name }}</span>
        </h3>
        <Button v-if="manageAvailable" variant="text" severity="secondary" @click.stop="openEdit">
          <template #icon>
            <EllipsisVertical :size="14" />
          </template>
        </Button>
      </div>

      <ul class="list">
        <li class="item">
          <span class="text">Id: </span>
          <UiId :id="data.id"></UiId>
        </li>
        <li class="item">
          <span class="text">Number of collections: </span>
          <span class="value"> {{ data.total_collections }}</span>
        </li>
        <li class="item">
          <span class="text">Created Date: </span>
          <span class="value"> {{ new Date(data.created_at).toLocaleDateString() }}</span>
        </li>
        <li class="item">
          <span class="text">Number of Members: </span>
          <span class="value"> {{ data.total_members }}</span>
        </li>
      </ul>
    </div>

    <div v-if="type === 'create'" class="content content--center">
      <template v-if="manageAvailable">
        <Button severity="secondary" rounded @click="$emit('createNew')">
          <template #icon>
            <Plus :size="14" />
          </template>
        </Button>
        <h3 class="title">Add new Orbit</h3>
        <p class="text">Start by creating an Orbit to organize your team's work</p>
      </template>
      <template v-else>
        <Lock :size="35" color="var(--p-primary-color)" />
        <h3 class="title">No Orbits available</h3>
        <p class="text">Ask your admin to create one so you can start collaborating</p>
      </template>
    </div>
  </article>
  <OrbitEditor v-if="data" v-model:visible="editVisible" :orbit="data"></OrbitEditor>
</template>

<script setup lang="ts">
import type { Orbit as OrbitType } from '@/lib/api/DataforceApi.interfaces'
import { ref } from 'vue'
import { Plus, Lock, Orbit, EllipsisVertical } from 'lucide-vue-next'
import { Button } from 'primevue'
import OrbitEditor from '../editor/OrbitEditor.vue'
import UiId from '@/components/ui/UiId.vue'

type Props = {
  type: 'default' | 'create'
  data?: OrbitType
  manageAvailable: boolean
}

type Emits = {
  createNew: []
}

defineProps<Props>()
defineEmits<Emits>()

const editVisible = ref(false)

function openEdit() {
  editVisible.value = true
}
</script>

<style scoped>
.card {
  height: 177px;
  padding: 16px 20px;
  border-radius: 8px;
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  box-shadow: var(--card-shadow);
  display: flex;
  flex-direction: column;
  justify-content: center;
}
.card--clickable {
  cursor: pointer;
  transition: background-color 0.3s;
}
.card--clickable:hover {
  background-color: var(--p-autocomplete-chip-focus-background);
}
.content--center {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 8px;
}
.header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  margin-bottom: 12px;
}
.title {
  font-size: 16px;
  font-weight: 500;
  display: flex;
  gap: 6px;
  align-items: center;
}
.list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  line-height: 1.66;
}
.item {
  font-size: 12px;
}
.text {
  font-size: 12px;
  color: var(--p-text-muted-color);
}
.circle {
  display: flex;
  justify-content: center;
  align-items: center;
}
.icon {
  flex: 0 0 auto;
}
</style>
