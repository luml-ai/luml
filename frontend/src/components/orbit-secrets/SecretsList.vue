<template>
  <DataTable
    :value="secretsStore.secretsList"
    dataKey="id"
    class="secrets-table"
  >
    <template #empty>
      <div class="placeholder">
        No secrets yet. Add your first secret to store API keys, tokens, and
        other sensitive data securely.
      </div>
    </template>

    <Column field="name" header="Secret name" style="width: 190px">
      <template #body="{ data }">
        <div class="secret-name-wrap">{{ data.name }}</div>
      </template>
    </Column>

    <Column field="value" header="Key" style="width: 190px">
      <template #body="{ data }">
        <div class="secret-key-wrap">
          <span v-if="!visibleSecrets[data.id]" class="secret-hidden">
            {{ '*'.repeat(data.value?.length) }}
          </span>
          <span v-else class="secret-revealed">{{ data.value }}</span>
        </div>
      </template>
    </Column>

    <Column field="tags" header="Tags" style="width: 190px">
      <template #body="{ data }">
        <div class="tags">
          <Tag v-for="tag in normalizeTags(data.tags)" :key="tag" class="tag">
            <span>{{ tag }}</span>
          </Tag>
        </div>
      </template>
    </Column>

    <Column field="updated_at" header="Updated" style="width: 190px">
      <template #body="{ data }">
        <div class="updated-date">
          {{ data.updated_at ? new Date(data.updated_at).toLocaleDateString() : new Date().toLocaleDateString() }}
        </div>
      </template>
    </Column>

    <Column style="width: 67px">
      <template #body="{ data }">
        <div class="actions">
          <Button
            variant="text"
            severity="secondary"
            rounded
            size="small"
            @click="toggleMenu($event, data.id)"
          >
            <template #icon>
              <EllipsisVertical :size="14" />
            </template>
          </Button>

          <Menu
            :model="getMenuItems(data)"
            :popup="true"
            :ref="el => menuRefs[data.id] = el"
            :pt="{
            root: { style: 'background: white;' },
          }"
          >
          </Menu>
        </div>
      </template>
    </Column>
  </DataTable>
  <SecretEditor v-model:visible="editDialogVisible" :secret="secretToEdit" />
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { DataTable, Column, Button, Tag, Menu, useToast } from 'primevue'
import { useSecretsStore } from '@/stores/orbit-secrets'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import SecretEditor from './SecretsEditor.vue'
import type { OrbitSecret } from '@/lib/api/orbit-secrets/interfaces'
import { EllipsisVertical } from 'lucide-vue-next'

interface Props {
  organizationId: number
  editAvailable?: boolean
  deleteAvailable?: boolean
  copyAvailable?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  editAvailable: true,
  deleteAvailable: true,
})

const menuRefs: Record<string, any> = {}

const secretsStore = useSecretsStore()
const toast = useToast()

const visibleSecrets = reactive<Record<number, boolean>>({})
const editDialogVisible = ref(false)
const secretToEdit = ref<OrbitSecret | null>(null)


function toggleMenu(event: Event, id: string) {
  menuRefs[id]?.toggle(event)
}

function getMenuItems(secret: OrbitSecret) {
  const items = []

  if (props.copyAvailable) {
    items.push({
      label: 'Copy',
      color: 'var(--p-primary-color)',
      command: () => copySecret(secret),
    })
  }

  if (props.editAvailable) {
    items.push({
      label: 'Settings',
      color: 'var(--p-primary-color)',
      command: () => editSecret(secret),
    })
  }
  return items
}

const editSecret = (secret: OrbitSecret) => {
  secretToEdit.value = secret
  editDialogVisible.value = true
}

const copySecret = async (secret: OrbitSecret) => {
  try {
    if (secret.value) {
      await navigator.clipboard.writeText(secret.value);
      toast.add(simpleSuccessToast(`Secret "${secret.name}" copied to clipboard`));
    } else {
      toast.add(simpleErrorToast(`Secret "${secret.name}" has no value to copy`));
    }
  } catch (e) {
    toast.add(simpleErrorToast(`Failed to copy secret "${secret.name}"`));
    console.error("Copy secret error:", e);
  }
}

function normalizeTags(tags: any): string[] {
  if (!tags) return []
  if (Array.isArray(tags)) {
    return tags.map(tag => typeof tag === 'string' ? tag : tag.name ?? '')
  }
  if (typeof tags === 'string') {
    return tags.split(',').map(tag => tag.trim())
  }
  return []
}
</script>

<style scoped>
.secrets-table {
  background: white;
  border-radius: 12px;
  overflow: hidden;
  box-shadow:
    0 1px 3px 0 rgba(0, 0, 0, 0.1),
    0 1px 2px -1px rgba(0, 0, 0, 0.1);
  border: 1px solid #e5e7eb;
}

.secrets-table :deep(.p-datatable-thead > tr > th) {
  background: white;
  border-bottom: 1px solid #e5e7eb;
  color: #334155;
  font-weight: 500;
  padding: 16px;
}

.secrets-table :deep(.p-datatable-tbody > tr > td) {
  background: white;
  border-left: none;
  border-right: none;
  border-bottom: 1px solid #f3f4f6;
  padding: 16px;
}

.secrets-table :deep(.p-datatable-table) {
  background: white;
}

.secrets-table :deep(.p-datatable-tbody > tr > td) {
  white-space: normal;
  word-wrap: break-word;
  vertical-align: top;
}
.secret-name-wrap,
.secret-key-wrap {
  white-space: normal;
  word-wrap: break-word;
  overflow-wrap: anywhere;
  font-size: 16px;
  color: #334155;
}

.secret-hidden,
.secret-revealed {
  display: block;
  white-space: normal;
  word-wrap: break-word;
  overflow-wrap: anywhere;
  color: #334155;
  font-weight: 400;
  font-size: 16px;
}

.placeholder {
  padding: 12px 0px;
  color: #334155;
  background: white;
}

.secret-name {
  font-weight: 400;
  color: #334155;
  font-size: 16px;
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

.updated-date {
  color: #6b7280;
  font-size: 16px;
}
</style>
