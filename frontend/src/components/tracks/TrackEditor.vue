<template>
  <UiDialogRight
    :visible="tracksStore.editorVisible"
    :icon="Bolt"
    title="TRACK settings"
    :footer-actions="footerActions"
    @update:visible="updateVisible"
  >
    <Form
      v-slot="$form"
      id="track-edit-form"
      :initialValues
      :resolver="resolver"
      class="form"
      @submit="submit"
    >
      <div class="inputs">
        <div class="field">
          <label for="name" class="label">Name</label>
          <InputText id="name" name="name" placeholder="Name your track" fluid />
          <Message v-if="$form.name?.invalid" severity="error" size="small" variant="simple">
            {{ $form.name.error?.message }}
          </Message>
        </div>
        <div class="field">
          <label for="description" class="label">Description</label>
          <Textarea
            name="description"
            id="description"
            placeholder="Describe your track"
            class="textarea"
            fluid
          ></Textarea>
          <Message v-if="$form.description?.invalid" severity="error" size="small" variant="simple">
            {{ $form.description.error?.message }}
          </Message>
        </div>
        <div class="field">
          <label for="stages" class="label">Stages</label>
          <UiTagsSelect
            v-model="initialValues.stages"
            id="stages"
            name="stages"
            placeholder="Type to add stages"
            :items="['Production', 'Pre-Production', 'Staging']"
            :itemsTooltips="stagesTooltips"
            :disabledValues="lockedStages"
          />
          <Message v-if="$form.stages?.invalid" severity="error" size="small" variant="simple">
            {{ $form.stages.error?.message }}
          </Message>
        </div>
      </div>
    </Form>
  </UiDialogRight>
</template>

<script setup lang="ts">
import type { TrackStage, TrackUpdateIn } from '@/lib/api/orbit-tracks/interfaces'
import { InputText, Message, Textarea, useToast, useConfirm } from 'primevue'
import { useTracksStore } from '@/stores/tracks'
import { Bolt } from 'lucide-vue-next'
import { computed, ref, watch } from 'vue'
import { Form, type FormSubmitEvent } from '@primevue/forms'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { getErrorMessage, type ApiError } from '@/helpers/helpers'
import { deleteTrackConfirmOptions } from '@/lib/primevue/data/confirm'
import { zodResolver } from '@primevue/forms/resolvers/zod'
import z from 'zod'
import UiDialogRight, { type FooterActions } from '../ui/dialogs/UiDialogRight.vue'
import UiTagsSelect from '../ui/UiTagsSelect.vue'

const tracksStore = useTracksStore()
const toast = useToast()
const confirm = useConfirm()

const initialValues = ref<{ name: string; description: string; stages: string[] }>({
  name: '',
  description: '',
  stages: [],
})

const resolver = zodResolver(
  z.object({
    name: z.string().min(1, 'Name is required').max(100, 'Name must be at most 100 characters'),
    description: z.string().max(1000, 'Description must be at most 1000 characters').optional(),
    stages: z
      .array(z.string())
      .refine(
        (stages) => stages.length > 0 || !stagesChanged(stages),
        'At least one stage is required',
      )
      .refine((stages) => stages.every((stage) => stage.length > 0), 'Stage name is required')
      .refine(
        (stages) => stages.every((stage) => stage.length <= 100),
        'Stage names must be at most 100 characters',
      ),
  }),
)

const deleteLoading = ref(false)
const saveLoading = ref(false)

const footerActions = computed<FooterActions>(() => {
  return {
    leftButton: {
      props: {
        label: 'Delete track',
        severity: 'warn',
        variant: 'outlined',
        loading: deleteLoading.value,
        onClick: onDeleteClick,
      },
    },
    rightButton: {
      props: {
        label: 'Save changes',
        type: 'submit',
        form: 'track-edit-form',
        loading: saveLoading.value,
      },
    },
  }
})

const stagesTooltips = computed(() => {
  return lockedStages.value.reduce(
    (acc, stage) => {
      acc[stage] = `This stage was linked to an artifact. To remove it, unlink the stage.`
      return acc
    },
    {} as Record<string, string>,
  )
})

const lockedStages = computed(() => {
  return (
    tracksStore.editableTrack?.stages.filter((stage) => stage.is_used).map((stage) => stage.name) ??
    []
  )
})

function stagesChanged(names: string[]) {
  const original = tracksStore.editableTrack?.stages.map((stage) => stage.name) ?? []
  return names.length !== original.length || names.some((name, index) => name !== original[index])
}

function buildStagesPayload(snapshot: TrackStage[], names: string[]) {
  return {
    stages: names.map((name) => {
      const existingStage = snapshot.find((stage) => stage.name === name)
      return existingStage ? { id: existingStage.id, name } : { name }
    }),
    expected_stage_ids: snapshot.map((stage) => stage.id),
  }
}

async function reloadStages(trackId: string) {
  const stages = await tracksStore.refreshTrackStages(trackId)
  initialValues.value.stages = stages.map((stage) => stage.name)
}

function updateVisible(visible: boolean) {
  if (!visible) tracksStore.hideEditor()
}

function onDeleteClick() {
  confirm.require(deleteTrackConfirmOptions(deleteTrack))
}

async function deleteTrack() {
  try {
    if (!tracksStore.editableTrack?.id) throw new Error('Track ID is required')
    deleteLoading.value = true
    await tracksStore.deleteTrack(tracksStore.editableTrack.id)
    toast.add(simpleSuccessToast('Track has been successfully deleted'))
    tracksStore.hideEditor()
  } catch (error) {
    toast.add(simpleErrorToast(getErrorMessage(error, 'Failed to delete track')))
  } finally {
    deleteLoading.value = false
  }
}

async function submit({ values, valid, reset }: FormSubmitEvent) {
  if (!valid) return
  const { name, description, stages } = values
  const track = tracksStore.editableTrack
  const sendsStages = !!track && stagesChanged(stages)
  try {
    saveLoading.value = true
    if (!track?.id) throw new Error('Track ID is required')
    const payload: TrackUpdateIn = { name, description }
    if (sendsStages) Object.assign(payload, buildStagesPayload(track.stages, stages))
    await tracksStore.updateTrack(track.id, payload)
    reset()
    tracksStore.hideEditor()
    toast.add(simpleSuccessToast('Track has been successfully updated'))
  } catch (error) {
    toast.add(simpleErrorToast(getErrorMessage(error, 'Failed to update track')))
    if (sendsStages && track && (error as ApiError)?.response?.status === 409) {
      await reloadStages(track.id).catch(() => undefined)
    }
  } finally {
    saveLoading.value = false
  }
}

watch(
  () => tracksStore.editableTrack,
  (track) => {
    initialValues.value.name = track?.name ?? ''
    initialValues.value.description = track?.description ?? ''
    initialValues.value.stages = track?.stages.map((stage) => stage.name) ?? []
  },
  { immediate: true },
)
</script>

<style scoped>
.header-content {
  display: flex;
  align-items: center;
  gap: 8px;
}
.footer-actions {
  width: 100%;
  display: flex;
  gap: 10px;
  justify-content: space-between;
}
.inputs {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 28px;
}
.field {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 7px;
}
.textarea {
  height: 72px;
  resize: none;
}
</style>
