import { ref, reactive, computed, watch } from 'vue'
import type { Ref } from 'vue'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import type { AutoCompleteCompleteEvent } from 'primevue/autocomplete'

import { useSecretsStore } from '@/stores/orbit-secrets'
import { useOrbitsStore } from '@/stores/orbits'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import type { CreateSecretPayload, UpdateSecretPayload } from '@/stores/orbit-secrets'
import type { OrbitSecret } from '@/lib/api/orbit-secrets/interfaces'

/**
 * @property {() => void} onSuccess
 */
interface UseSecretFormOptions {
  onSuccess: () => void;
}

/**
 * @param secret
 * @param options
 */
export function useSecretForm(secret: Ref<OrbitSecret | null | undefined>, options: UseSecretFormOptions) {
  const secretsStore = useSecretsStore()
  const orbitsStore = useOrbitsStore()
  const toast = useToast()
  const confirm = useConfirm()

  const isEditMode = computed(() => !!secret.value?.id)

  const form = reactive({
    name: '',
    value: '',
    tags: [] as string[],
  })
  const errors = reactive({ name: '', value: '' })

  const isSubmitting = ref(false) 
  const isDeleting = ref(false)  
  const isLoadingDetails = ref(false)

  const autocompleteItems = ref<string[]>([])
  const existingTags = computed(() => secretsStore.existingTags)

  function searchTags(event: AutoCompleteCompleteEvent) {
    const query = event.query.toLowerCase()
    autocompleteItems.value = [
      event.query,
      ...existingTags.value.filter((tag: string) => tag.toLowerCase().includes(query)),
    ]
  }

  const resetForm = () => {
    form.name = ''
    form.value = ''
    form.tags = []
    errors.name = ''
    errors.value = ''
  }

  resetForm()

  const loadSecretDetails = async () => {
    if (!isEditMode.value || !secret.value) return
    
    isLoadingDetails.value = true
    resetForm()
    try {
      const currentOrbit = orbitsStore.currentOrbitDetails
      if (currentOrbit?.organization_id && currentOrbit?.id) {
        const fullSecret = await secretsStore.getSecretById(
          currentOrbit.organization_id, currentOrbit.id, secret.value.id
        )
        if (fullSecret) {
          form.name = fullSecret.name || ''
          form.value = fullSecret.value || ''
          form.tags = [...(fullSecret.tags || [])]
        }
      }
    } catch (e: any) {
      toast.add(simpleErrorToast(e.message || 'Failed to load secret details'))
      options.onSuccess()
    } finally {
      isLoadingDetails.value = false
    }
  }

  watch(secret, (newSecret, oldSecret) => {
    if (newSecret?.id) {
      loadSecretDetails()
    } else {
      resetForm()
    }
  }, { immediate: true })


  const validateForm = (): boolean => {
    errors.name = ''
    errors.value = ''
    let isValid = true

    if (!form.name.trim()) {
      errors.name = 'Secret name is required'
      isValid = false
    } else if (form.name.trim().length < 2) {
      errors.name = 'Secret name must be at least 2 characters'
      isValid = false
    } else {
      const existingSecret = secretsStore.secretsList.find(
        s => s.name.toLowerCase() === form.name.trim().toLowerCase() && s.id !== secret.value?.id
      )
      if (existingSecret) {
        errors.name = 'A secret with this name already exists'
        isValid = false
      }
    }

    if (!isEditMode.value && !form.value.trim()) {
      errors.value = 'Secret value is required'
      isValid = false
    }
    
    return isValid
  }

  const handleSubmit = async () => {
    if (!validateForm()) return

    isSubmitting.value = true
    try {
      const currentOrbit = orbitsStore.currentOrbitDetails
      if (!currentOrbit?.organization_id || !currentOrbit?.id) {
        throw new Error("Current orbit details are not available.")
      }

      const payload = {
        name: form.name.trim(),
        value: form.value.trim(),
        tags: form.tags,
      }
      
      if (isEditMode.value && secret.value) {
        const updatePayload: UpdateSecretPayload = { id: secret.value.id, ...payload }
        await secretsStore.updateSecret(currentOrbit.organization_id, currentOrbit.id, updatePayload)
        toast.add(simpleSuccessToast('Secret updated successfully'))
      } else {
        await secretsStore.addSecret(currentOrbit.organization_id, currentOrbit.id, payload as CreateSecretPayload)
        toast.add(simpleSuccessToast('Secret created successfully'))
      }

      options.onSuccess()
    } catch (e: any) {
      toast.add(simpleErrorToast(e?.response?.data?.detail || e.message || 'An unknown error occurred'))
    } finally {
      isSubmitting.value = false
    }
  }

  const handleDelete = () => {
    if (!isEditMode.value || !secret.value) return

    confirm.require({
      message: 'This action is permanent and cannot be undone. Are you sure you want to delete this secret?', 
      header: 'Delete key?',
      acceptLabel: 'Delete',
      rejectLabel: 'Cancel',
      acceptProps: {
        severity: 'warn',
        variant: 'outlined',
      },
      accept: async () => {
        isDeleting.value = true
        try {
          const currentOrbit = orbitsStore.currentOrbitDetails
          if (currentOrbit?.organization_id && currentOrbit?.id && secret.value?.id) {
            await secretsStore.deleteSecret(currentOrbit.organization_id, currentOrbit.id, secret.value.id)
            toast.add(simpleSuccessToast('Secret deleted successfully'))
            options.onSuccess() 
          }
        } catch (e: any) {
          toast.add(simpleErrorToast(e.message || 'Failed to delete secret'))
        } finally {
          isDeleting.value = false
        }
      }
    })
  }

  return {
    form,
    errors,
    isEditMode,
    isSubmitting,
    isDeleting,
    isLoadingDetails,
    autocompleteItems,
    searchTags,
    handleSubmit,
    handleDelete,
    resetForm, 
  }
}