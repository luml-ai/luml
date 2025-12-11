<template>
  <Dialog
    v-model:visible="visible"
    position="topright"
    :draggable="false"
    style="margin-top: 80px; height: 86%; width: 420px"
    :pt="dialogPT"
  >
    <template #header>
      <h2 class="dialog-title">
        <Bolt :size="20" color="var(--p-primary-color)" />
        <span>Model settings</span>
      </h2>
    </template>
    <Form
      id="orbit-edit-form"
      :initialValues
      :resolver="modelEditorResolver"
      class="form"
      @submit="saveChanges"
    >
      <div class="form-item">
        <label for="name" class="label">Name</label>
        <InputText v-model="initialValues.name" name="name" id="name" />
      </div>
      <div class="form-item">
        <label for="description" class="label">Description</label>
        <Textarea
          v-model="initialValues.description"
          name="description"
          id="description"
          placeholder="Describe your model"
          style="height: 72px; resize: none"
        ></Textarea>
      </div>
      <div class="form-item">
        <label for="tags" class="label">Tags</label>
        <AutoComplete
          v-model="initialValues.tags"
          id="tags"
          name="tags"
          placeholder="Type to add tags"
          fluid
          multiple
          :suggestions="autocompleteItems"
          @complete="searchTags"
        ></AutoComplete>
      </div>
    </Form>
    <template #footer>
      <div>
        <Button
          v-if="orbitsStore.getCurrentOrbitPermissions?.model.includes(PermissionEnum.delete)"
          variant="outlined"
          severity="warn"
          :disabled="loading"
          @click="onDeleteClick"
        >
          delete model
        </Button>
      </div>
      <Button type="submit" :loading="loading" form="orbit-edit-form"> save changes </Button>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import type { UpdateMlModelPayload } from '@/lib/api/orbit-ml-models/interfaces'
import type { SelectedModel } from '../CollectionModelsTable.vue'
import { computed, ref } from 'vue'
import {
  type DialogPassThroughOptions,
  Dialog,
  Button,
  InputText,
  Textarea,
  AutoComplete,
  useToast,
  useConfirm,
  type AutoCompleteCompleteEvent,
} from 'primevue'
import { Bolt } from 'lucide-vue-next'
import { Form } from '@primevue/forms'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { deleteModelConfirmOptions } from '@/lib/primevue/data/confirm'
import { modelEditorResolver } from '@/utils/forms/resolvers'
import { useOrbitsStore } from '@/stores/orbits'
import { PermissionEnum } from '@/lib/api/api.interfaces'
import { useModelsStore } from '@/stores/models'

const dialogPT: DialogPassThroughOptions = {
  footer: {
    style: 'display: flex; justify-content: space-between; width: 100%; margin-top: auto;',
  },
}

type Props = {
  data: SelectedModel
}

const props = defineProps<Props>()

const visible = defineModel<boolean>('visible')
const emit = defineEmits(['model-deleted'])

const toast = useToast()
const confirm = useConfirm()
const orbitsStore = useOrbitsStore()
const modelsStore = useModelsStore()

const initialValues = ref({
  name: props.data.model_name,
  description: props.data.description,
  tags: [...props.data.tags],
})
const loading = ref(false)
const existingTags = computed(() => {
  const tagsSet = modelsStore.modelsList.reduce((acc: Set<string>, item) => {
    item.tags.map((tag) => {
      acc.add(tag)
    })
    return acc
  }, new Set<string>())
  return Array.from(tagsSet)
})
const autocompleteItems = ref<string[]>([])

function searchTags(event: AutoCompleteCompleteEvent) {
  autocompleteItems.value = [
    event.query,
    ...existingTags.value.filter((tag) => tag.toLowerCase().includes(event.query.toLowerCase())),
  ]
}

async function saveChanges() {
  try {
    loading.value = true
    const payload: UpdateMlModelPayload = {
      id: props.data.id,
      file_name: props.data.file_name,
      model_name: initialValues.value.name,
      description: initialValues.value.description,
      tags: initialValues.value.tags,
    }
    await modelsStore.updateModel(payload)
    toast.add(simpleSuccessToast('Model successfully updated'))
    visible.value = false
  } catch (e) {
    toast.add(simpleErrorToast('Failed to update model'))
  } finally {
    loading.value = false
  }
}

function onDeleteClick() {
  confirm.require(deleteModelConfirmOptions(deleteModel, 1))
}

async function deleteModel() {
  try {
    loading.value = true
    const result = await modelsStore.deleteModels([props.data.id])
    if (result.deleted?.length) {
      toast.add(
        simpleSuccessToast(`Model "${props.data.model_name}" was removed from the collection.`),
      )
      emit('model-deleted')
      visible.value = false
      await new Promise((resolve) => setTimeout(resolve, 100))
    } else if (result.failed?.length) {
      toast.add(simpleErrorToast(`Failed to delete model "${props.data.model_name}".`))
    }
  } catch (e) {
    toast.add(simpleErrorToast('Failed to delete model'))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.dialog-title {
  font-weight: 500;
  font-size: 16px;
  text-transform: uppercase;
  display: flex;
  gap: 8px;
  align-items: center;
}
.form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.form-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.label {
  font-weight: 500;
  align-self: flex-start;
}
</style>
