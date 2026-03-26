<template>
  <div>
    <Select
      v-model="modelValue"
      :options="secretsList"
      filter
      filter-placeholder="Select secret"
      option-label="name"
      option-value="id"
      placeholder="Select secret"
      size="small"
      fluid
    >
      <template #footer>
        <div class="select-footer">
          <Button variant="text" @click="initCreateSecret">
            <Plus :size="14"></Plus>
            Add new secret
          </Button>
        </div>
      </template>
    </Select>
    <SecretCreator
      v-if="isCreating"
      v-model:visible="isCreating"
      :organization-id="String($route.params.organizationId)"
      :orbit-id="String($route.params.id)"
    ></SecretCreator>
  </div>
</template>

<script setup lang="ts">
import type { OrbitSecret } from '@/lib/api/orbit-secrets/interfaces'
import { Select, Button } from 'primevue'
import { Plus } from 'lucide-vue-next'
import { ref } from 'vue'
import SecretCreator from '@/components/orbit-secrets/SecretCreator.vue'

type Props = {
  secretsList: OrbitSecret[]
}

defineProps<Props>()

const modelValue = defineModel<string | null>('modelValue')

const isCreating = ref(false)

function initCreateSecret() {
  isCreating.value = true
}
</script>

<style scoped>
.select-footer {
  margin: 0 8px;
  padding: 4px 0;
  border-top: 1px solid var(--p-divider-border-color);
}
</style>
