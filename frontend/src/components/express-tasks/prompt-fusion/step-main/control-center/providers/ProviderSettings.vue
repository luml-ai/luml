<template>
  <d-dialog
    :visible="modelValue"
    modal
    style="width: 100%; max-width: 597px"
    dismissable-mask
    @update:visible="(value: boolean) => $emit('update:modelValue', value)"
  >
    <template #header>
      <h2 class="dialog-title">setup {{ providerName }}</h2>
    </template>
    <div class="items">
      <div v-for="setting in settingsState" class="item">
        <label :for="setting.id" class="label" :class="{ required: setting.required }">{{
          setting.label
        }}</label>
        <d-input-text
          :id="setting.id"
          v-model="setting.value"
          :placeholder="setting.placeholder"
          fluid
        />
      </div>
    </div>
    <div class="save-key">
      <d-checkbox v-model="saveApiKey" inputId="saveKey" class="checkbox" binary />
      <label for="saveKey" class="label">Allow storing API key in browser's local storage</label>
    </div>
    <template #footer>
      <d-button label="Save" @click="onSave" />
    </template>
  </d-dialog>
</template>

<script setup lang="ts">
import type { ProviderSetting } from '@/lib/promt-fusion/prompt-fusion.interfaces'
import { onBeforeMount, ref, watch } from 'vue'
import { LocalStorageService } from '@/utils/services/LocalStorageService'

type Props = {
  providerName: string
  modelValue: boolean
  settings: ProviderSetting[]
}
type Emits = {
  'update:modelValue': [boolean]
  save: [ProviderSetting[]]
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const saveApiKey = ref(false)
const settingsState = ref<ProviderSetting[]>(JSON.parse(JSON.stringify(props.settings)))

function onSave() {
  emit('save', JSON.parse(JSON.stringify(settingsState.value)))
}

onBeforeMount(() => {
  const settings = LocalStorageService.get('providersSettings')
  saveApiKey.value = !!settings?.saveApiKeys
})

watch(saveApiKey, (val) => {
  const settings = LocalStorageService.get('providersSettings') || {}
  settings.saveApiKeys = val
  LocalStorageService.set('providersSettings', settings)
})
</script>

<style scoped>
.dialog-title {
  font-size: 20px;
  font-weight: 600;
  text-transform: uppercase;
}
.items {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-bottom: 24px;
}
.item {
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.label {
  font-size: 14px;
  line-height: 1.5;
}
.label.required::after {
  content: ' *';
  color: var(--p-badge-danger-background);
}
.save-key {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-bottom: 24px;
}
.checkbox {
  flex: 0 0 auto;
}
.label {
  cursor: pointer;
}
</style>
