import { WorkspaceRefusedError } from '@/api/slices/workspace/workspace.api'
import type { ConfirmationOptions } from 'primevue/confirmationoptions'
import { deleteFlowConfirmOptions } from '@/confirm/confirm'
import type { IWorkspaceFolderItem } from './interface'

export const FILE_PATH_NOTE = 'Cells that read this file by path are not updated.'
export const ENTRY_DIALOG_PT = {
  root: { class: 'w-[600px] max-w-[95vw] rounded-lg!' },
  header: { class: 'text-xl uppercase' },
  content: { class: 'pb-7' },
}

export function invalidName(name: string) {
  if (name === '') return 'Name is required'
  if (name === '.' || name === '..' || /[/\\]/.test(name) || name.includes('\0'))
    return 'Enter a single name without path separators.'
  return ''
}

export function operationError(error: unknown) {
  if (!(error instanceof WorkspaceRefusedError)) return error
  if (error.kind === 'Protected') return new Error('This directory is protected.')
  if (error.kind === 'NotAFile')
    return new Error('This operation is unavailable for notebook or internal files.')
  return error
}

export function deleteConfirmation(item: IWorkspaceFolderItem): ConfirmationOptions {
  const options = deleteFlowConfirmOptions(() => {})
  if (item.type === 'flow') return options
  const permanent = 'This action is permanent and cannot be undone.'
  const message =
    item.type === 'file'
      ? `${permanent} Cells that read this file will fail the next time they run.`
      : item.is_symlink
        ? `Only the symbolic link is deleted. ${permanent}`
        : `The folder and everything in it are deleted. ${permanent}`
  return {
    ...options,
    header: `Delete ${item.name}?`,
    message,
    acceptProps: { ...options.acceptProps, label: `Delete ${item.type}` },
  }
}
