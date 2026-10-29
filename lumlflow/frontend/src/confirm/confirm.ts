import type { ConfirmationOptions } from 'primevue/confirmationoptions'
import type { Experiment } from '@/store/experiments/experiments.interface'

const PERMANENT_ACTION_MESSAGE = 'This action is permanent and cannot be undone.'

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
  experiments: Experiment[] = [],
): ConfirmationOptions => {
  const multiple = experiments.length > 1
  const flowOrigins = experiments
    .map(formatLumlflowOrigin)
    .filter((origin): origin is string => origin !== null)
  const flowWarning = flowOrigins.length
    ? ` ${flowOrigins.length === 1 ? 'This experiment was' : 'These experiments were'} produced by lumlflow: ${flowOrigins.join('; ')}.`
    : ''

  return {
    group: 'delete',
    message: `${PERMANENT_ACTION_MESSAGE}${flowWarning}`,
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

export const deleteFlowConfirmOptions = (accept: () => void): ConfirmationOptions => {
  return {
    message: PERMANENT_ACTION_MESSAGE,
    header: 'Delete notebook?',
    acceptProps: {
      label: 'Delete notebook',
      severity: 'warn',
      variant: 'outlined',
    },
    rejectProps: {
      label: 'Cancel',
    },
    accept,
  }
}

export const deleteCellConfirmOptions = (accept: () => void, slug: string): ConfirmationOptions => {
  return {
    message: `${PERMANENT_ACTION_MESSAGE} Every other lane keeps its own copy of \`${slug}\`.`,
    header: 'Delete cell from this lane?',
    acceptProps: {
      label: 'Delete cell',
      severity: 'warn',
      variant: 'outlined',
    },
    rejectProps: {
      label: 'Cancel',
    },
    accept,
  }
}

export const moveLaneConfirmOptions = (
  accept: () => void,
  { lane, step, isLatest }: { lane: string; step: number; isLatest: boolean },
): ConfirmationOptions => {
  return {
    message: isLatest
      ? `Lane ${lane} will move to its latest step ${step}.`
      : `Lane ${lane} will move to step ${step}. You can return to its latest step at any time.`,
    header: `Move to step ${step}?`,
    acceptProps: {
      label: `Move to step ${step}`,
    },
    rejectProps: {
      label: 'Cancel',
      variant: 'outlined',
    },
    accept,
  }
}

function formatLumlflowOrigin(experiment: Experiment): string | null {
  const origin = experiment.metadata.lumlflow
  if (typeof origin !== 'object' || origin === null || Array.isArray(origin)) return null

  const { flow, slug, lane } = origin as Record<string, unknown>
  if (
    typeof flow !== 'string' ||
    flow.length === 0 ||
    typeof slug !== 'string' ||
    slug.length === 0 ||
    typeof lane !== 'string' ||
    lane.length === 0
  ) {
    return null
  }
  return `${flow} / ${slug} on lane ${lane}`
}
