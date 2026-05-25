export const userProfileUpdateSuccessToast = (detail) => ({
    severity: 'success',
    summary: 'Success',
    detail: detail || 'User profile updated successfully',
    life: 3000,
});
export const passwordChangedSuccessToast = {
    severity: 'success',
    summary: 'Success',
    detail: 'Password has been changed!',
    life: 3000,
};
export const emailSentVerifyToast = {
    severity: 'success',
    summary: 'Email sent',
    detail: 'Thanks! An email was sent to verify your account. If you don’t receive an email, please contact us.',
    life: 3000,
};
export const passwordResetSuccessToast = {
    severity: 'success',
    summary: 'Success',
    detail: 'Password has been changed!',
    life: 3000,
};
export const trainingErrorToast = (detail) => ({
    severity: 'error',
    summary: 'Error',
    detail: detail || 'Training error. Change data for training.',
    life: 10000,
});
export const predictErrorToast = (detail) => ({
    severity: 'error',
    summary: 'Error',
    detail: detail || 'Prediction error. Data is not correct.',
    life: 10000,
});
export const incorrectFileTypeErrorToast = {
    severity: 'error',
    summary: 'Error',
    detail: 'This file format is not supported',
    life: 10000,
};
export const incorrectTargetWarning = {
    severity: 'warn',
    summary: 'Warning',
    detail: 'The group cannot be the target',
    life: 3000,
};
export const incorrectGroupWarning = {
    severity: 'warn',
    summary: 'Warning',
    detail: 'Target cannot be part of a group',
    life: 3000,
};
export const selectProviderErrorToast = {
    severity: 'error',
    summary: 'Provider Error',
    detail: 'The provider must be connected',
    life: 3000,
};
export const unknownErrorToast = {
    severity: 'error',
    summary: 'Error',
    detail: 'An unknown error has occurred',
    life: 3000,
};
export const simpleSuccessToast = (detail, title) => ({
    severity: 'success',
    summary: title || 'Success',
    detail: detail,
    life: 3000,
});
export const simpleErrorToast = (detail, title) => ({
    severity: 'error',
    summary: title || 'Error',
    detail: detail,
    life: 3000,
});
export const simpleWardToast = (detail, title) => ({
    severity: 'warn',
    summary: title || 'Warn',
    detail: detail,
    life: 3000,
});
