import type { Ref } from 'vue'

export interface FileNode {
  name: string
  path?: string
  type: 'file' | 'folder'
  size?: number
  children?: FileNode[]
}

export type PreviewState = 'loading' | 'unsupported' | 'too-big' | 'empty' | 'error' | null

export type FileContentError = 'unsupported' | 'not-found' | 'empty' | 'too-big' | 'unknown'

export interface AttachmentContent {
  blob: Blob
  size: number
}

export interface ModelAttachmentsProvider {
  getTree(): FileNode[]
  getAttachmentContent(path: string): Promise<AttachmentContent>
  isEmpty(): boolean
}

export interface FileContentResult {
  blob?: Blob
  text?: string
  contentUrl?: string
  error?: FileContentError
}

export interface UseFilePreviewOptions {
  file: Ref<FileNode | null>
  provider: Ref<ModelAttachmentsProvider>
}

export interface FileNodeProps {
  node: FileNode
  selected: FileNode | null
}

export interface FileNodeEmits {
  (e: 'select', node: FileNode): void
}

export interface FilePreviewHeaderProps {
  fileName: string
  fileSize: number
  filePath: string
}

export interface FilePreviewHeaderEmits {
  (e: 'copy-path'): void
  (e: 'download'): void
}

export interface PreviewStatesProps {
  state: PreviewState
  errorMessage?: string
}

export interface ImagePreviewProps {
  contentUrl: string
  fileName: string
}

export interface SvgPreviewProps {
  contentUrl: string
  fileName: string
}

export interface MediaPreviewProps {
  type: 'audio' | 'video'
  contentUrl: string
}

export interface PdfPreviewProps {
  contentUrl: string
}

export interface HtmlPreviewProps {
  contentUrl: string
}

export interface TablePreviewProps {
  contentBlob: Blob
  fileName: string
}

export interface CodePreviewProps {
  textContent: string
  fileName: string
}
