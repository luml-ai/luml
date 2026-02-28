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
        <span>Artifact settings</span>
      </h2>
    </template>
    <Form
      id="orbit-edit-form"
      :initialValues
      :resolver="artifactEditResolver"
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
          placeholder="Describe your artifact"
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
          v-if="orbitsStore.getCurrentOrbitPermissions?.artifact.includes(PermissionEnum.delete)"
          variant="outlined"
          severity="warn"
          :disabled="loading"
          @click="onDeleteClick"
        >
          delete artifact
        </Button>
      </div>
      <Button type="submit" :loading="loading" form="orbit-edit-form"> save changes </Button>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import type { Artifact, UpdateArtifactPayload } from '@/lib/api/artifacts/interfaces'
import { ref, watch } from 'vue'
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
import { deleteArtifactConfirmOptions } from '@/lib/primevue/data/confirm'
import { artifactEditResolver } from '@/utils/forms/resolvers'
import { useOrbitsStore } from '@/stores/orbits'
import { PermissionEnum } from '@/lib/api/api.interfaces'
import { useArtifactsStore } from '@/stores/artifacts'
import { useArtifactsTags } from '@/hooks/useArtifactsTags'
import { getErrorMessage } from '@/helpers/helpers'

const dialogPT: DialogPassThroughOptions = {
  footer: {
    style: 'display: flex; justify-content: space-between; width: 100%; margin-top: auto;',
  },
}

type Props = {
  data: Artifact
}

type Emits = {
  (e: 'updateArtifact', artifact: Artifact): void
  (e: 'artifactDeleted'): void
}

const props = defineProps<Props>()

const emit = defineEmits<Emits>()

const visible = defineModel<boolean>('visible')

const toast = useToast()
const confirm = useConfirm()
const orbitsStore = useOrbitsStore()
const artifactsStore = useArtifactsStore()
const { getTagsByQuery, loadTags } = useArtifactsTags()

const initialValues = ref({
  name: props.data.name,
  description: props.data.description,
  tags: [...(props.data.tags || [])],
})
const loading = ref(false)
const autocompleteItems = ref<string[]>([])

function searchTags(event: AutoCompleteCompleteEvent) {
  autocompleteItems.value = getTagsByQuery(event.query)
}

async function saveChanges() {
  try {
    loading.value = true
    const payload: UpdateArtifactPayload = {
      id: props.data.id,
      file_name: props.data.file_name,
      name: initialValues.value.name,
      description: initialValues.value.description,
      tags: initialValues.value.tags,
    }
    const result = await artifactsStore.updateArtifact(payload)
    emit('updateArtifact', result)
    toast.add(simpleSuccessToast('Artifact successfully updated'))
    visible.value = false
  } catch (e) {
    toast.add(simpleErrorToast('Failed to update artifact'))
  } finally {
    loading.value = false
  }
}

function onDeleteClick() {
  confirm.require(deleteArtifactConfirmOptions(deleteArtifact, 1))
}

async function deleteArtifact() {
  try {
    loading.value = true
    const result = await artifactsStore.deleteArtifacts([props.data.id])
    if (result.deleted?.length) {
      toast.add(
        simpleSuccessToast(`Artifact "${props.data.name}" was removed from the collection.`),
      )
      visible.value = false
      emit('artifactDeleted')
    } else if (result.failed?.length) {
      toast.add(simpleErrorToast(`Failed to delete artifact "${props.data.name}".`))
    }
  } catch (e) {
    toast.add(simpleErrorToast('Failed to delete artifact'))
  } finally {
    loading.value = false
  }
}

watch(
  () => artifactsStore.requestInfo,
  async (info) => {
    try {
      autocompleteItems.value = []
      if (!info) return
      await loadTags(info.organizationId, info.orbitId, info.collectionId)
    } catch (e) {
      const message = getErrorMessage(e, 'Failed to load tags')
      toast.add(simpleErrorToast(message))
    }
  },
  { immediate: true, deep: true },
)
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
