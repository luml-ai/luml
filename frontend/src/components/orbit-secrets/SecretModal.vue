<template>
  <Dialog v-model:visible="visible" header="Key" :pt="dialogPt" modal :draggable="false">
    <div>
      <InputGroup>
        <InputText :value="loading ? 'Loading...' : secretValue" :disabled="loading" readonly />
        <InputGroupAddon>
          <Button variant="text" severity="secondary" style="height: 100%" @click="copySecret">
            <Copy :size="14" />
          </Button>
        </InputGroupAddon>
      </InputGroup>
    </div>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Dialog, InputText, InputGroup, InputGroupAddon, Button, useToast } from 'primevue'
import type { DialogPassThroughOptions } from 'primevue'
import { Copy } from 'lucide-vue-next'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import type { OrbitSecret } from '@/lib/api/orbit-secrets/interfaces'
import { useSecretsStore } from '@/stores/orbit-secrets'
import { useOrbitsStore } from '@/stores/orbits'

interface Props {
  secret: OrbitSecret | null
}
const props = defineProps<Props>()
const visible = defineModel<boolean>('visible')

const toast = useToast()
const secretsStore = useSecretsStore()
const orbitsStore = useOrbitsStore()
const secretValue = ref('')
const loading = ref(false)

watch(visible, (val) => {
  if (val && props.secret) loadSecretValue(props.secret.id)
})

const dialogPt: DialogPassThroughOptions = {
  root: {
    style: 'width: 600px;'
  },
  header: {
    style: 'text-transform: uppercase; padding: 36px 36px 28px;'
  },
  content: {
    style: 'padding: 0 36px 36px;'
  },
  footer: {
    style: 'display: flex; justify-content: flex-end; padding: 0 36px 36px;'
  },
}


async function loadSecretValue(secretId: number) {
  const orbit = orbitsStore.currentOrbitDetails
  if (!orbit?.organization_id || !orbit?.id) return

  try {
    loading.value = true
    const fullSecret = await secretsStore.getSecretById(
      orbit.organization_id,
      orbit.id,
      secretId
    )
    secretValue.value = fullSecret?.value || ''
  } catch (error) {
    toast.add(simpleErrorToast('You don’t have access to view this key.'))
  } finally {
    loading.value = false
  }
}

async function copySecret() {
  if (!secretValue.value) return
  try {
    await navigator.clipboard.writeText(secretValue.value)
    toast.add(simpleSuccessToast('Secret copied to clipboard'))
  } catch (e) {
    toast.add(simpleErrorToast('Failed to copy secret'))
    console.error('Copy secret error:', e)
  }
}
</script>
