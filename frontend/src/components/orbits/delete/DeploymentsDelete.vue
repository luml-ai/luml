<template>
  <Dialog
    v-model:visible="visible"
    modal
    :draggable="false"
    header="Stop this deployment?"
    :style="{ width: '350px' }"
  >
    <div>
      <p class="text">
        This action will schedule a task for your satellite to shut down this deployment.
      </p>
      <div class="checkbox-wrapper">
        <Checkbox v-model="accept" inputId="deleteAccept" binary />
        <label for="deleteAccept">Yes, stop this deployment</label>
      </div>
    </div>
    <template #footer>
      <Button @click="visible = false" :disabled="loading">cancel</Button>
      <Button
        severity="warn"
        outlined
        :disabled="!accept"
        :loading="loading"
        @click="deleteDeployment"
      >
        stop
      </Button>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Checkbox, Button, Dialog, useToast } from 'primevue'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { useDeploymentsStore } from '@/stores/deployments'
import { getErrorMessage } from '@/helpers/helpers'

type Props = {
  organizationId: string
  orbitId: string
  deploymentId: string
  name: string
}

type Emits = {
  delete: []
}

const props = defineProps<Props>()
const emits = defineEmits<Emits>()

const toast = useToast()
const deploymentsStore = useDeploymentsStore()

const visible = defineModel<boolean>('visible')

const accept = ref(false)
const loading = ref(false)

async function deleteDeployment() {
  try {
    loading.value = true
    await deploymentsStore.deleteDeployment(props.organizationId, props.orbitId, props.deploymentId)
    toast.add(simpleSuccessToast(`Deployment "${props.name}" is shutting down.`))
    emits('delete')
  } catch (e: any) {
    toast.add(simpleErrorToast(getErrorMessage(e, 'Could not delete deployment')))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.text {
  margin-bottom: 14px;
}

.checkbox-wrapper {
  display: flex;
  align-items: center;
  gap: 7px;
}
</style>
