<template>
  <div>
    <Button @click="visible = true">
      <Plus :size="14" />
      <span>New relay</span>
    </Button>
    <Dialog
      v-model:visible="visible"
      modal
      :draggable="false"
      style="max-width: 500px; width: 100%"
      :pt="dialogPT"
    >
      <template #header>
        <h2 class="creator-title">Add a relay</h2>
      </template>
      <RelayForm v-model="formData" form-id="relayCreateForm" @submit="create" />
      <Button type="submit" form="relayCreateForm" fluid rounded :loading="loading" class="submit">
        Create
      </Button>
    </Dialog>
    <RelayTokenDialog v-if="token" :token="token" @close="token = null" />
  </div>
</template>

<script setup lang="ts">
import type { RelayCreatePayload } from '@/lib/api/relays/interfaces'
import type { DialogPassThroughOptions } from 'primevue'
import { ref } from 'vue'
import { Button, Dialog, useToast } from 'primevue'
import { Plus } from 'lucide-vue-next'
import { useRelaysStore } from '@/stores/relays'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { getErrorMessage } from '@/helpers/helpers'
import RelayForm from './RelayForm.vue'
import RelayTokenDialog from './RelayTokenDialog.vue'

type Props = {
  organizationId: string
}

const dialogPT: DialogPassThroughOptions = {
  header: {
    style: 'padding: 28px;',
  },
  content: {
    style: 'padding: 0 28px 28px',
  },
}

const props = defineProps<Props>()
const relaysStore = useRelaysStore()
const toast = useToast()

const visible = ref(false)
const loading = ref(false)
const token = ref<string | null>(null)
const formData = ref<RelayCreatePayload>({ label: '', base_domain: '', agent_url: '' })

async function create() {
  try {
    loading.value = true
    token.value = await relaysStore.createRelay(props.organizationId, { ...formData.value })
    visible.value = false
    formData.value = { label: '', base_domain: '', agent_url: '' }
    toast.add(simpleSuccessToast('New relay has been added.'))
  } catch (error: unknown) {
    toast.add(simpleErrorToast(getErrorMessage(error, 'Failed to create relay')))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.creator-title {
  font-size: 20px;
  font-weight: 600;
  text-transform: uppercase;
}
.submit {
  margin-top: 20px;
}
</style>
