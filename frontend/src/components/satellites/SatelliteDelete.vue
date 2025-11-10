<template>
  <Dialog
    v-model:visible="visible"
    modal
    :draggable="false"
    header="Unpair this satellite?"
    :style="{ width: '350px' }"
  >
    <div>
      <p class="text">This action will unpair the satellite {{ name }} from your orbit.</p>
      <div class="checkbox-wrapper">
        <Checkbox v-model="accept" inputId="deleteAccept" binary />
        <label for="deleteAccept">Yes, unpair this satellite</label>
      </div>
    </div>
    <template #footer>
      <Button @click="visible = false" :disabled="loading">cancel</Button>
      <Button
        severity="warn"
        outlined
        :disabled="!accept"
        :loading="loading"
        @click="deleteSatellite"
      >
        unpair
      </Button>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Dialog, Button, Checkbox, useToast } from 'primevue'
import { useSatellitesStore } from '@/stores/satellites'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { getErrorMessage } from '@/helpers/helpers'

type Props = {
  organizationId: string
  orbitId: string
  satelliteId: string
  name: string
}

type Emits = {
  delete: []
}

const props = defineProps<Props>()
const emits = defineEmits<Emits>()

const visible = defineModel<boolean>('visible')
const toast = useToast()
const satellitesStore = useSatellitesStore()
const loading = ref(false)
const accept = ref(false)

async function deleteSatellite() {
  try {
    loading.value = true
    await satellitesStore.deleteSatellite(props.organizationId, props.orbitId, props.satelliteId)
    toast.add(simpleSuccessToast(`Satellite "${props.name}" deleted successfully.`))
    emits('delete')
    visible.value = false
  } catch (e: any) {
    toast.add(simpleErrorToast(getErrorMessage(e, 'Could not delete satellite')))
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
