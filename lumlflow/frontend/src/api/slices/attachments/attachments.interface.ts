export interface GetAttachmentsParams {
  parent_path?: string
}

export interface GetAttachmentsResponseItem {
  name: string
  type: 'file' | 'folder'
  path?: string
  size?: number | null
}

export interface GetAttachmentContentParams {
  file_path: string
}
