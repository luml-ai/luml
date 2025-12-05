<template>
  <div class="simple-table">
    <div class="simple-table__header">
      <div class="simple-table__row">
        <div>Secret name</div>
        <div>Key</div>
        <div>Tags</div>
        <div>Updated</div>
        <div></div>
      </div>
    </div>
    <div class="simple-table__rows">
      <div v-if="!secretsStore.secretsList.length" class="simple-table__placeholder">
        You don’t have any secrets yet.
      </div>
      <div v-for="secret in secretsStore.secretsList" :key="secret.id" class="simple-table__row">
        <div class="secret-name">
          {{ secret.name }}
        </div>
        <div class="secret-key">
          <Button
            variant="text"
            severity="secondary"
            class="eye-button"
            @click="showSecretModal(secret)"
          >
            <template #icon>
              <Eye :size="15" />
            </template>
          </Button>
          <span v-if="!visibleSecrets[secret.id]" class="secret-hidden">
            {{ maskSecret(secret.value) }}
          </span>
          <span v-else class="secret-revealed">{{ secret.value }}</span>
        </div>
        <div class="tags">
          <Tag v-for="tag in normalizeTags(secret.tags)" :key="tag" class="tag">
            <span>{{ tag }}</span>
          </Tag>
        </div>
        <div class="updated-date">
          {{
            secret.updated_at
              ? new Date(secret.updated_at).toLocaleString()
              : new Date().toLocaleString()
          }}
        </div>

        <div class="actions">
          <Button variant="text" severity="secondary" @click="editSecret(secret)">
            <template #icon>
              <Bolt :size="14" />
            </template>
          </Button>
        </div>
      </div>
    </div>
  </div>

  <SecretModal v-model:visible="secretModalVisible" :secret="currentSecret" />

  <SecretEditor v-model:visible="editDialogVisible" :secret="secretToEdit" />
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { Button, Tag } from 'primevue'
import { useSecretsStore } from '@/stores/orbit-secrets'
import type { OrbitSecret } from '@/lib/api/orbit-secrets/interfaces'
import SecretEditor from './SecretsEditor.vue'
import SecretModal from './SecretModal.vue'
import { Eye, Bolt } from 'lucide-vue-next'

const secretsStore = useSecretsStore()

const visibleSecrets = reactive<Record<string, boolean>>({})

const editDialogVisible = ref(false)
const secretToEdit = ref<OrbitSecret | null>(null)

const secretModalVisible = ref(false)
const currentSecret = ref<OrbitSecret | null>(null)

type Props = {
  organizationId: string
  editAvailable?: boolean
  copyAvailable?: boolean
}

defineProps<Props>()

const editSecret = (secret: OrbitSecret) => {
  secretToEdit.value = secret
  editDialogVisible.value = true
}

function showSecretModal(secret: OrbitSecret) {
  currentSecret.value = secret
  secretModalVisible.value = true
}

function maskSecret(value?: string): string {
  if (!value) return '*'.repeat(30)
  return value.length > 30 ? '*'.repeat(30) : '*'.repeat(value.length)
}

function normalizeTags(tags: any): string[] {
  if (!tags) return []
  if (Array.isArray(tags)) {
    return tags.map((tag) => (typeof tag === 'string' ? tag : (tag.name ?? '')))
  }
  if (typeof tags === 'string') {
    return tags.split(',').map((tag) => tag.trim())
  }
  return []
}
</script>

<style scoped>
@import '@/assets/tables.css';

.simple-table__header .simple-table__row,
.simple-table__rows .simple-table__row {
  display: grid;
  grid-template-columns: 1.3fr 1.5fr 1fr 1fr 40px;
  align-items: center;
}

.tags {
  overflow-x: auto;
  display: flex;
  gap: 10px;
  padding-bottom: 4px;
  row-gap: 4px;
  flex-wrap: wrap;
}

.tag {
  font-size: 12px;
  font-weight: 400;
}

.actions {
  display: flex;
  align-items: center;
  justify-content: center;
}

.eye-button.p-button {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
}

.secret-name {
  word-wrap: break-word;
  overflow-wrap: anywhere;
}
</style>
