<template>
  <Dialog
    v-model:visible="visible"
    modal
    :draggable="false"
    :header="title"
    :style="{ width: '348px' }"
  >
    <div>
      <p class="text" v-html="text"></p>
      <InputText v-model="input" placeholder="delete" fluid size="small" />
    </div>
    <template #footer>
      <Button @click="visible = false" :disabled="loading">cancel</Button>
      <Button
        severity="warn"
        outlined
        :disabled="confirmDisabled || loading"
        :loading="loading"
        @click="$emit('confirm')"
      >
        force delete
      </Button>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { Dialog, Button, InputText } from 'primevue'
import { computed, ref, watch } from 'vue'

type Props = {
  title: string
  text: string
  loading: boolean
}

type Emits = {
  confirm: []
}

defineProps<Props>()

defineEmits<Emits>()

const visible = defineModel<boolean>('visible')

const input = ref('')

const confirmDisabled = computed(() => {
  return input.value !== 'delete'
})

watch(visible, (val) => {
  if (val) return
  input.value = ''
})
</script>

<style scoped>
.text {
  font-size: 14px;
  line-height: 1.63;
  margin-bottom: 22px;
}
</style>
