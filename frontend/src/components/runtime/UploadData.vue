<template>
  <div class="wrapper">
    <h1 class="title">Upload your model</h1>
    <div class="area">
      <file-input
        id="model"
        :file="file"
        :error="isError"
        accept-text="Accepts .luml files"
        upload-text="upload a model"
        :loading="isModelLoading"
        loading-message="Model creating..."
        @select-file="selectFile"
        @remove-file="removeFile"
      />
      <span class="middle-divider">or</span>
      <div class="sample">
        <div class="sample-title">
          <span>Don't have a model yet? Train one in “Express tasks”</span>
        </div>
        <d-button label="Express tasks" @click="$router.push({ name: 'home' })" />
      </div>
    </div>
    <div class="navigation">
      <d-button :disabled="!isContinueAvailable" @click="$emit('continue')">
        Continue <ArrowRight width="14" height="14" />
      </d-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import FileInput from '../ui/FileInput.vue'
import { ArrowRight } from 'lucide-vue-next'
import { predictErrorToast } from '@/lib/primevue/data/toasts'
import { useToast } from 'primevue'

const toast = useToast()

type Props = {
  uploadCallback: Function
  removeCallback: Function
}
type Emits = {
  continue: void
}
type FileData = {
  name?: string
  size?: number
}

const props = defineProps<Props>()
defineEmits<Emits>()

const file = ref<FileData>({})
const isModelLoading = ref(false)
const isError = ref(false)

const isContinueAvailable = computed(() => !!file.value.name)

async function selectFile(event: File) {
  isError.value = false
  isModelLoading.value = true
  try {
    await props.uploadCallback(event)

    file.value = {
      name: event.name,
      size: event.size,
    }
  } catch (e) {
    toast.add(predictErrorToast(e as string))
    isError.value = true
  } finally {
    isModelLoading.value = false
  }
}
function removeFile() {
  isError.value = false
  file.value = {}
  props.removeCallback()
}
</script>

<style scoped>
.wrapper {
  padding-top: 32px;
}
.title {
  margin-bottom: 24px;
}
.area {
  padding: 36px;
  border-radius: 8px;
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  box-shadow: var(--card-shadow);
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.middle-divider {
  font-weight: 500;
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 10px;
  align-items: center;
  color: var(--p-text-muted-color);
}
.middle-divider::before,
.middle-divider::after {
  content: '';
  height: 1px;
  background-color: var(--p-divider-border-color);
}
.sample {
  padding: 24px;
  border: 1px solid var(--p-content-border-color);
  display: flex;
  flex-direction: column;
  gap: 16px;
  align-items: flex-start;
  border-radius: 8px;
}
.sample-title {
  font-weight: 500;
}
.navigation {
  position: fixed;
  bottom: 0;
  right: 0;
  padding: 4px 100px 44px 0;
  width: 100%;
  background-color: var(--p-content-background);
  display: flex;
  justify-content: flex-end;
}
</style>
