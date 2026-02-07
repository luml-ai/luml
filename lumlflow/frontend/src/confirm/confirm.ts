import type { ConfirmationOptions } from 'primevue/confirmationoptions'

export const deleteGroupConfirmOptions = (
  accept: () => void,
  multiple = false,
): ConfirmationOptions => {
  return {
    group: 'delete',
    message: 'This action is permanent and cannot be undone.',
    header: multiple ? 'Delete selected groups?' : 'Delete group?',
    acceptProps: {
      label: multiple ? 'delete groups' : 'delete group',
    },
    rejectProps: {
      label: 'cancel',
    },
    accept,
  }
}

export const deleteExperimentConfirmOptions = (
  accept: () => void,
  multiple = false,
): ConfirmationOptions => {
  return {
    group: 'delete',
    message: 'This action is permanent and cannot be undone.',
    header: multiple ? 'Delete selected experiments?' : 'Delete experiment?',
    acceptProps: {
      label: multiple ? 'delete experiments' : 'delete experiment',
    },
    rejectProps: {
      label: 'cancel',
    },
    accept,
  }
}
