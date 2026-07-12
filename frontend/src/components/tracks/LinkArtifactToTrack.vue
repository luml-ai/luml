<template>
  <Button
    variant="text"
    severity="secondary"
    v-tooltip="'Link to track'"
    @click="visible = true"
  >
    <template #icon>
      <TrainTrack :size="14" />
    </template>
  </Button>
  <UiDialogRight
    v-model:visible="visible"
    :icon="TrainTrack"
    title="LINK ARTIFACT TO TRACK"
    :footer-actions="footerActions"
  >
    <Form
      ref="formRef"
      id="link-artifact-to-track-form"
      :initialValues
      :resolver
      class="form"
      @submit="onSubmit"
    >
      <TracksSelect
        name="track_id"
        :disabled="false"
        :organization-id="organizationId"
        :orbit-id="orbitId"
        required
        :types="[props.artifactType]"
        :hidden-tracks="props.existingTracks.map((track) => track.id)"
      />
      <StageSelect :options="tracksStore.trackStages" />
      <StageWarning v-if="artifactWithSelectedStage" :artifact="artifactWithSelectedStage" />
    </Form>
  </UiDialogRight>
</template>

<script setup lang="ts">
import type { ArtifactTrack, ArtifactTypeEnum } from '@/lib/api/artifacts/interfaces'
import type { TrackEntry, TrackEntryCreateIn } from '@/lib/api/orbit-tracks/interfaces'
import { Form, type FormInstance, type FormSubmitEvent } from '@primevue/forms'
import { computed, onBeforeUnmount, ref, watch, watchEffect } from 'vue'
import { Button, useToast } from 'primevue'
import { zodResolver } from '@primevue/forms/resolvers/zod'
import { TrainTrack } from 'lucide-vue-next'
import { useRoute } from 'vue-router'
import { useTracksStore } from '@/stores/tracks'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { getErrorMessage } from '@/helpers/helpers'
import { useArtifactLinksStore } from '@/stores/artifact-links/artifact-links'
import z from 'zod'
import TracksSelect from './TracksSelect.vue'
import UiDialogRight, { type FooterActions } from '../ui/dialogs/UiDialogRight.vue'
import StageSelect from './StageSelect.vue'
import StageWarning from './StageWarning.vue'

interface Props {
  artifactId: string
  artifactType: ArtifactTypeEnum
  existingTracks: ArtifactTrack[]
}

interface Emits {
  (e: 'tracks-changed'): void
}

const props = defineProps<Props>()

const emit = defineEmits<Emits>()

const route = useRoute()

const toast = useToast()

const tracksStore = useTracksStore()

const artifactLinksStore = useArtifactLinksStore()

const organizationId = computed(() => String(route.params.organizationId))
const orbitId = computed(() => String(route.params.id))
const footerActions = computed<FooterActions>(() => {
  return {
    rightButton: {
      props: {
        label: 'Link to track',
        type: 'submit',
        form: 'link-artifact-to-track-form',
        loading: saveLoading.value,
        disabled: submitDisabled.value,
      },
    },
  }
})

const formRef = ref<FormInstance>()

const visible = ref(false)

const saveLoading = ref(false)

const stagesLoading = ref(false)

const artifactWithSelectedStage = ref<TrackEntry | null>(null)

const initialValues = computed(() => {
  return {
    track_id: '',
    stage_id: '',
  }
})

const resolver = zodResolver(
  z.object({
    track_id: z.string().min(1).max(100),
    stage_id: z.string().min(1).max(100).optional(),
  }),
)

const submitDisabled = computed(() => {
  return !formRef.value?.valid || !!artifactWithSelectedStage.value
})

async function getTrackStages(trackId: string) {
  try {
    stagesLoading.value = true
    await tracksStore.listStages(trackId)
  } catch {
    toast.add(simpleErrorToast('Failed to load stages'))
  } finally {
    stagesLoading.value = false
  }
}

async function onSubmit({ valid, values }: FormSubmitEvent) {
  if (!valid) return

  try {
    saveLoading.value = true
    const { track_id, stage_id } = values
    const payload: TrackEntryCreateIn = {
      artifact_id: props.artifactId,
    }
    if (stage_id) {
      payload.stage_id = stage_id
    }
    await artifactLinksStore.addEntry(track_id, payload)
    emit('tracks-changed')
    toast.add(simpleSuccessToast('Artifact linked to track'))
    visible.value = false
  } catch (error) {
    toast.add(simpleErrorToast(getErrorMessage(error, 'Failed to link artifact to track')))
  } finally {
    saveLoading.value = false
  }
}

async function getArtifactWithSelectedStage(trackId: string, stageId: string) {
  try {
    artifactWithSelectedStage.value = await artifactLinksStore.getEntryByStage(trackId, stageId)
  } catch {
    artifactWithSelectedStage.value = null
  }
}

watch(
  () => formRef.value?.states.track_id.value,
  (value) => {
    if (value) {
      formRef.value?.setFieldValue('stage_id', undefined)
      getTrackStages(value)
    } else {
      tracksStore.resetTrackStages()
    }
  },
)

watch(visible, (value) => {
  if (value) {
    formRef.value?.reset()
  }
})

watchEffect(() => {
  const trackId = formRef.value?.getFieldState('track_id')?.value
  const stageId = formRef.value?.getFieldState('stage_id')?.value
  if (!trackId || !stageId) {
    artifactWithSelectedStage.value = null
    return
  }
  getArtifactWithSelectedStage(trackId, stageId)
})

onBeforeUnmount(() => {
  tracksStore.reset()
})
</script>

<style scoped>
.dialog-title {
  display: flex;
  align-items: center;
  gap: 8px;
}
.footer-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
.form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.label {
  font-weight: 500;
  align-self: flex-start;
}
</style>
