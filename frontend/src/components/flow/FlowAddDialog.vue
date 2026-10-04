<template>
  <Dialog
    v-model:visible="visible"
    header="Add a flow"
    :pt="dialogPt"
    modal
    :draggable="false"
    @after-hide="reset"
  >
    <div class="choices">
      <button
        type="button"
        class="choice"
        :class="{ 'choice--active': choice === 'local' }"
        data-testid="choice-local"
        @click="choice = 'local'"
      >
        <Laptop :size="20" />
        <span class="choice__title">Local</span>
        <span class="choice__text">On this computer</span>
      </button>
      <button
        type="button"
        class="choice"
        :class="{ 'choice--active': choice === 'relayed' }"
        data-testid="choice-relayed"
        @click="choice = 'relayed'"
      >
        <Globe :size="20" />
        <span class="choice__title">Relayed</span>
        <span class="choice__text">On a remote machine</span>
      </button>
    </div>

    <form
      v-if="choice === 'local'"
      class="fields"
      data-testid="local-form"
      @submit.prevent="addLocal"
    >
      <div class="field">
        <label for="flow-address" class="label required">Address</label>
        <InputText v-model="address" id="flow-address" name="address" fluid />
      </div>
      <div class="field">
        <label for="flow-port" class="label required">Port</label>
        <InputNumber
          v-model="port"
          input-id="flow-port"
          name="port"
          :min="1"
          :max="65535"
          :use-grouping="false"
          fluid
        />
      </div>
      <div class="field">
        <label for="flow-name" class="label">Name</label>
        <InputText v-model="name" id="flow-name" name="name" :placeholder="defaultName" fluid />
      </div>
      <p v-if="error" class="error" data-testid="local-error">{{ error }}</p>
      <Button label="Add" type="submit" fluid rounded :loading="checking" />
    </form>

    <div v-else-if="choice === 'relayed'" class="relayed" data-testid="relayed-info">
      <template v-if="orbitHasRelay">
        <p>Expose a Flow from a remote machine with the LUML SDK.</p>
        <a :href="RELAYED_FLOWS_DOCS_URL" target="_blank" class="link" data-testid="docs-link">
          Read how to expose a flow
        </a>
      </template>
      <template v-else>
        <p>This orbit has no relay.</p>
        <router-link
          :to="{ name: 'organization-orbits', params: { organizationId } }"
          class="link"
          data-testid="orbits-link"
        >
          Assign a relay in the orbit settings
        </router-link>
      </template>
    </div>
  </Dialog>
</template>

<script setup lang="ts">
import type { DialogPassThroughOptions } from 'primevue'
import type { LocalFlow } from '@/utils/services/LocalStorageService.interfaces'
import { computed, ref } from 'vue'
import { Button, Dialog, InputNumber, InputText } from 'primevue'
import { Globe, Laptop } from 'lucide-vue-next'
import {
  isLocalFlowReachable,
  localFlowExistsMessage,
  localFlowKey,
  useLocalFlowsStore,
} from '@/stores/local-flows'
import { RELAYED_FLOWS_DOCS_URL } from './flow-commands'

type Props = {
  organizationId: string
  orbitHasRelay: boolean
}

type Emits = {
  added: [LocalFlow]
}

defineProps<Props>()
const emit = defineEmits<Emits>()

const visible = defineModel<boolean>('visible')

const dialogPt: DialogPassThroughOptions = {
  root: {
    style: 'max-width: 500px; width: 100%;',
  },
  header: {
    style: 'padding: 28px; text-transform: uppercase; font-size: 20px;',
  },
  content: {
    style: 'padding: 0 28px 28px;',
  },
}

const DEFAULT_ADDRESS = 'localhost'
const DEFAULT_PORT = 5000

const localFlowsStore = useLocalFlowsStore()

const choice = ref<'local' | 'relayed' | null>(null)
const address = ref(DEFAULT_ADDRESS)
const port = ref<number | null>(DEFAULT_PORT)
const name = ref('')
const error = ref<string | null>(null)
const checking = ref(false)

const defaultName = computed(() => `${address.value.trim()}:${port.value ?? ''}`)

async function addLocal() {
  error.value = null
  const entry = { address: address.value.trim(), port: port.value }
  if (!entry.address || entry.port === null) {
    error.value = 'Enter an address and a port.'
    return
  }
  const flow: LocalFlow = {
    name: name.value.trim() || defaultName.value,
    address: entry.address,
    port: entry.port,
  }
  const existing = localFlowsStore.findLocalFlow(flow)
  if (existing) {
    error.value = localFlowExistsMessage(existing)
    return
  }
  try {
    checking.value = true
    if (!(await isLocalFlowReachable(flow))) {
      error.value = `No Flow at ${localFlowKey(flow)}. This page can reach only localhost.`
      return
    }
  } finally {
    checking.value = false
  }
  localFlowsStore.addLocalFlow(flow)
  emit('added', flow)
  visible.value = false
}

function reset() {
  choice.value = null
  address.value = DEFAULT_ADDRESS
  port.value = DEFAULT_PORT
  name.value = ''
  error.value = null
}
</script>

<style scoped>
.choices {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 20px;
}

.choice {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  padding: 16px;
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
  background-color: var(--p-card-background);
  color: var(--p-text-color);
  text-align: left;
  cursor: pointer;
}

.choice:hover {
  background-color: var(--p-content-hover-background);
}

.choice--active {
  border-color: var(--p-primary-color);
}

.choice__title {
  font-weight: 500;
}

.choice__text {
  font-size: 12px;
  color: var(--p-text-muted-color);
}

.fields {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.error {
  font-size: 14px;
  color: var(--p-message-error-color);
}

.relayed {
  display: flex;
  flex-direction: column;
  gap: 12px;
  font-size: 14px;
  line-height: 20px;
}

.link {
  color: var(--p-primary-color);
}
</style>
