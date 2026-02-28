import type { ConfirmationOptions } from 'primevue/confirmationoptions'

export const deleteAnnotationConfirmOptions = (
  name: string,
  accept: () => void,
): ConfirmationOptions => ({
  message: 'This action is permanent and cannot be undone.',
  header: `Delete ${name}?`,
  rejectProps: {
    label: 'Cancel',
  },
  acceptProps: {
    label: 'Delete annotation',
    severity: 'warn',
    outlined: true,
  },
  accept,
})
