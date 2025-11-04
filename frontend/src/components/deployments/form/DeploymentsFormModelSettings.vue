<template>
  <div class="column">
    <h4 class="column-title">Model</h4>
    <div class="fields">
      <div class="field">
        <label for="collectionId" class="label required">Collection</label>
        <Select
          v-model="collectionId"
          id="collectionId"
          name="collectionId"
          placeholder="Select collection"
          fluid
          :options="collections"
          option-label="name"
          option-value="id"
          :disabled="!!initialCollectionId"
        >
          <template #header>
            <div class="dropdown-title">Available collection</div>
          </template>
        </Select>
      </div>
      <div class="field" style="margin-bottom: 12px">
        <label for="modelId" class="label required">Model</label>
        <Select
          v-model="modelId"
          id="modelId"
          name="modelId"
          placeholder="Select model"
          fluid
          :options="modelsList"
          option-label="model_name"
          option-value="id"
          :disabled="!!initialModelId"
        >
          <template #header>
            <div class="dropdown-title">Available mdodel</div>
          </template>
        </Select>
      </div>
      <Accordion
        v-if="secretDynamicAttributes.length || secretEnvs.length"
        style="margin-bottom: 12px"
      >
        <template #expandicon>
          <ChevronDown :size="20"></ChevronDown>
        </template>
        <template #collapseicon>
          <ChevronUp :size="20"></ChevronUp>
        </template>
        <AccordionPanel value="0">
          <AccordionHeader>
            <div class="accordion-title">
              Secrets
              <HelpCircle :size="12" color="var(--p-button-text-secondary-color)"></HelpCircle>
            </div>
          </AccordionHeader>
          <AccordionContent>
            <FormField
              v-for="(secret, index) in secretEnvs"
              :key="secret.key"
              :name="`secretEnvs.${index}.value`"
              class="field"
            >
              <label class="label">{{ secret.label }} (env variables)</label>
              <SecretsSelect
                v-model="secret.value"
                :secrets-list="secretsStore.secretsList"
              ></SecretsSelect>
            </FormField>
            <FormField
              v-for="(secret, index) in secretDynamicAttributes"
              :key="secret.key"
              :name="`secretDynamicAttributes.${index}.value`"
              class="field"
            >
              <label class="label">{{ secret.label }} (dynamic attributes)</label>
              <SecretsSelect
                v-model="secret.value"
                :secrets-list="secretsStore.secretsList"
              ></SecretsSelect>
            </FormField>
          </AccordionContent>
        </AccordionPanel>
      </Accordion>
      <Accordion v-if="notSecretEnvs.length">
        <template #expandicon>
          <ChevronDown :size="20"></ChevronDown>
        </template>
        <template #collapseicon>
          <ChevronUp :size="20"></ChevronUp>
        </template>
        <AccordionPanel value="0">
          <AccordionHeader>
            <div class="accordion-title">
              Env variables (non-secret)
              <HelpCircle :size="12" color="var(--p-button-text-secondary-color)"></HelpCircle>
            </div>
          </AccordionHeader>
          <AccordionContent>
            <FormField
              v-for="(variable, index) in notSecretEnvs"
              :key="variable.key"
              :name="`notSecretEnvs.${index}.value`"
              class="field"
            >
              <label class="label">{{ variable.label }}</label>
              <InputText
                v-model="variable.value"
                placeholder="Enter value"
                size="small"
              ></InputText>
            </FormField>
          </AccordionContent>
        </AccordionPanel>
      </Accordion>

      <Button
        label="Add custom variable"
        variant="text"
        style="align-self: flex-start; padding: 8px"
        @click="addCustomVariable"
      >
        <template #icon>
          <Plus :size="14" />
        </template>
      </Button>

      <div v-if="customVariables.length" class="custom-variables">
        <div class="accordion-title">
          custom env variables
          <HelpCircle :size="12" color="var(--p-button-text-secondary-color)"></HelpCircle>
        </div>
        <div class="custom-variables__content">
          <div v-for="(item, index) in customVariables" :key="index" class="custom-variables__item">
            <FormField :name="`customVariables.${index}.key`">
              <InputText v-model="item.key" placeholder="Enter key" size="small" fluid></InputText>
            </FormField>
            <FormField :name="`customVariables.${index}.value`">
              <InputText
                v-model="item.value"
                placeholder="Enter value"
                size="small"
                fluid
              ></InputText>
            </FormField>
            <Button
              severity="secondary"
              variant="text"
              size="small"
              @click="removeCustomVariable(index)"
            >
              <template #icon>
                <Trash2 :size="14"></Trash2>
              </template>
            </Button>
          </div>
        </div>
      </div>
      <div v-if="dynamicAttributes?.length" class="dynamic-attributes">
        <div class="dynamic-attributes-message">
          <BellRing :size="14" class="dynamic-attributes-icon"></BellRing>
          <span>
            Pass dynamic attributes as parameters in the <br />
            inference payload
          </span>
        </div>
        <div class="dynamic-attributes-tags">
          <div
            v-for="attribute in dynamicAttributes"
            :key="attribute.key"
            class="dynamic-attributes-tag"
          >
            {{ attribute.label }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { FieldInfo } from '../deployments.interfaces'
import type { MlModel } from '@/lib/api/orbit-ml-models/interfaces'
import type { Manifest, Var } from '@fnnx/common/dist/interfaces'
import { getErrorMessage } from '@/helpers/helpers'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { useCollectionsStore } from '@/stores/collections'
import { useModelsStore } from '@/stores/models'
import {
  Select,
  useToast,
  Accordion,
  AccordionPanel,
  AccordionHeader,
  AccordionContent,
  InputText,
  Button,
} from 'primevue'
import { computed, onBeforeMount, ref, watch } from 'vue'
import { HelpCircle, ChevronDown, ChevronUp, Plus, BellRing, Trash2 } from 'lucide-vue-next'
import { useSecretsStore } from '@/stores/orbit-secrets'
import { FnnxService } from '@/lib/fnnx/FnnxService'
import { FormField } from '@primevue/forms'
import SecretsSelect from './SecretsSelect.vue'

type Props = {
  initialCollectionId?: string
  initialModelId?: string
}

const props = defineProps<Props>()

const collectionsStore = useCollectionsStore()
const modelsStore = useModelsStore()
const secretsStore = useSecretsStore()
const toast = useToast()

const modelsList = ref<MlModel[]>([])

const collectionId = defineModel<string | null>('collectionId')
const modelId = defineModel<string | null>('modelId')
const secretDynamicAttributes = defineModel<FieldInfo<string>[]>('secretDynamicAttributes', {
  default: [],
})
const secretEnvs = defineModel<FieldInfo<string>[]>('secretEnvs', {
  default: [],
})
const dynamicAttributes = defineModel<FieldInfo[]>('dynamicAttributes', {
  default: [],
})
const notSecretEnvs = defineModel<FieldInfo<string>[]>('notSecretEnvs', {
  default: [],
})
const customVariables = defineModel<Omit<FieldInfo<string>, 'label'>[]>('customVariables', {
  default: [],
})

const collections = computed(() => collectionsStore.collectionsList)
const selectedModel = computed(() => {
  if (!modelId.value) return null
  const model = modelsList.value.find((model) => model.id === modelId.value)
  return model || null
})

async function getCollections() {
  try {
    await collectionsStore.loadCollections()
  } catch (e: any) {
    toast.add(simpleErrorToast(getErrorMessage(e, 'Failed to load collections')))
  }
}

async function getModels(collectionId: string) {
  try {
    const { organizationId, orbitId } = collectionsStore.requestInfo
    modelsList.value = await modelsStore.getModelsList(organizationId, orbitId, collectionId)
    if (props.initialModelId) {
      modelId.value = props.initialModelId
    }
  } catch (e) {
    toast.add(simpleErrorToast(getErrorMessage(e, 'Failed to load models')))
  }
}

async function getSecrets() {
  try {
    const { organizationId, orbitId } = collectionsStore.requestInfo
    await secretsStore.loadSecrets(organizationId, orbitId)
  } catch (e) {
    toast.add(simpleErrorToast(getErrorMessage(e, 'Failed to load secrets')))
  }
}

function addCustomVariable() {
  customVariables.value?.push({ key: '', value: '' })
}

function onCollectionChange(collectionId: string | null | undefined) {
  modelsList.value = []
  if (collectionId) {
    getModels(collectionId)
  }
}

function onModelChange(model: MlModel | null) {
  customVariables.value = []
  if (model) {
    setDynamicAttributes(model.manifest)
    setEnvs(model.manifest)
  } else {
    secretDynamicAttributes.value = []
    dynamicAttributes.value = []
    secretEnvs.value = []
    notSecretEnvs.value = []
  }
}

function getFieldFromVar(attributeData: Var) {
  return {
    key: attributeData.name,
    label: attributeData.description || attributeData.name,
    value: null,
  }
}

function setDynamicAttributes(manifest: Manifest) {
  const { secrets, notSecrets } = FnnxService.getDynamicAttributes(manifest)
  secretDynamicAttributes.value = secrets.map(getFieldFromVar)
  dynamicAttributes.value = notSecrets.map(getFieldFromVar)
}

function setEnvs(manifest: Manifest) {
  const { secrets, notSecrets } = FnnxService.getEnvVars(manifest)
  secretEnvs.value = secrets.map(getFieldFromVar)
  notSecretEnvs.value = notSecrets.map(getFieldFromVar)
}

function removeCustomVariable(removeIndex: number) {
  customVariables.value = customVariables.value.filter((item, index) => index !== removeIndex)
}

watch(collectionId, onCollectionChange, { immediate: true })

watch(selectedModel, onModelChange, { immediate: true })

onBeforeMount(async () => {
  await getCollections()
  await getSecrets()
  if (props.initialCollectionId) {
    collectionId.value = props.initialCollectionId
  }
})
</script>

<style scoped>
.column {
  padding: 20px;
  overflow-y: auto;
  height: 100%;
  border-right: 1px solid var(--p-divider-border-color);
}

.column-title {
  font-weight: 500;
  margin-bottom: 20px;
}

.fields {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.textarea {
  resize: none;
  height: 72px;
}

:deep(.p-disabled .p-select-dropdown) {
  display: none;
}

.accordion-title {
  display: flex;
  align-items: center;
  gap: 4px;
  text-transform: uppercase;
  font-size: 12px;
  padding: 2px 0;
  font-weight: 500;
  color: var(--p-text-color);
}

:deep(.p-accordionheader) {
  padding: 12px;
}

:deep(.p-accordionpanel) {
  border: none;
}

:deep(.p-accordioncontent-content) {
  display: flex;
  flex-direction: column;
  gap: 16px;
  border-radius: 0 0 8px 8px;
  padding: 6px 12px 12px;
}

:deep(.p-accordioncontent-content) .label {
  font-size: 12px;
  line-height: 1.75;
}

.custom-variables {
  padding: 12px;
  border-radius: var(--p-border-radius-lg);
  background-color: var(--p-badge-secondary-background);
}

.custom-variables__content {
  padding-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.custom-variables__item {
  display: grid;
  grid-template-columns: 1fr 1fr auto;
  gap: 8px;
}

.dynamic-attributes {
  padding: 12px;
  border-radius: var(--p-border-radius-lg);
  border: 1px solid var(--p-content-border-color);
}

.dynamic-attributes-message {
  border-radius: var(--p-border-radius-lg);
  background-color: var(--p-tag-primary-background);
  padding: 8px 12px;
  display: flex;
  gap: 8px;
  align-items: flex-start;
  color: var(--p-tag-primary-color);
  font-size: 12px;
  margin-bottom: 16px;
}

.dynamic-attributes-icon {
  margin-top: 3px;
}

.dynamic-attributes-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.dynamic-attributes-tag {
  display: inline-block;
  padding: 4px 8px;
  border-radius: 6px;
  border-radius: var(--p-tag-border-radius);
  font-size: var(--p-tag-font-size);
  color: var(--p-tag-secondary-color);
  background-color: var(--p-tag-secondary-background);
}
.dropdown-title {
  padding: 12px 16px 8px;
  font-size: 14px;
  font-weight: var(--p-select-option-group-font-weight);
  color: var(--p-select-option-group-color);
}
</style>
