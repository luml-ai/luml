import type { ToastMessageOptions } from 'primevue'

export const userProfileUpdateSuccessToast = (detail?: string): ToastMessageOptions => ({
  severity: 'success',
  summary: 'Success',
  detail: detail || 'User profile updated successfully',
  life: 3000,
})

export const passwordChangedSuccessToast: ToastMessageOptions = {
  severity: 'success',
  summary: 'Success',
  detail: 'Password has been changed!',
  life: 3000,
}

export const emailSentVerifyToast: ToastMessageOptions = {
  severity: 'success',
  summary: 'Email sent',
  detail:
    'Thanks! An email was sent to verify your account. If you don’t receive an email, please contact us.',
  life: 3000,
}

export const passwordResetSuccessToast: ToastMessageOptions = {
  severity: 'success',
  summary: 'Success',
  detail: 'Password has been changed!',
  life: 3000,
}

export const trainingErrorToast = (detail?: string): ToastMessageOptions => ({
  severity: 'error',
  summary: 'Error',
  detail: detail || 'Training error. Change data for training.',
  life: 10000,
})

export const predictErrorToast = (detail?: string): ToastMessageOptions => ({
  severity: 'error',
  summary: 'Error',
  detail: detail || 'Prediction error. Data is not correct.',
  life: 10000,
})

export const incorrectFileTypeErrorToast: ToastMessageOptions = {
  severity: 'error',
  summary: 'Error',
  detail: 'This file format is not supported',
  life: 10000,
}

export const incorrectTargetWarning: ToastMessageOptions = {
  severity: 'warn',
  summary: 'Warning',
  detail: 'The group cannot be the target',
  life: 3000,
}

export const incorrectGroupWarning: ToastMessageOptions = {
  severity: 'warn',
  summary: 'Warning',
  detail: 'Target cannot be part of a group',
  life: 3000,
}

export const selectProviderErrorToast: ToastMessageOptions = {
  severity: 'error',
  summary: 'Provider Error',
  detail: 'The provider must be connected',
  life: 3000,
}

export const unknownErrorToast: ToastMessageOptions = {
  severity: 'error',
  summary: 'Error',
  detail: 'An unknown error has occurred',
  life: 3000,
}

export const simpleSuccessToast = (detail: string, title?: string): ToastMessageOptions => ({
  severity: 'success',
  summary: title || 'Success',
  detail: detail,
  life: 3000,
})

export const simpleErrorToast = (detail: string, title?: string): ToastMessageOptions => ({
  severity: 'error',
  summary: title || 'Error',
  detail: detail,
  life: 3000,
})

export const simpleWardToast = (detail: string, title?: string): ToastMessageOptions => ({
  severity: 'warn',
  summary: title || 'Warn',
  detail: detail,
  life: 3000,
})
