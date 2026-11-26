import type { AsyncBuffer } from 'hyparquet'

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
  supportsPartialPreview?(path: string): boolean
  getPreviewSource?(path: string, size?: number): PreviewSource | Promise<PreviewSource>
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

export type PreviewSource = string | Blob | AsyncBuffer

export interface FilePreviewProps {
  fileName: string
  fileSize?: number
  supportsPartialPreview?: boolean
  source: PreviewSource | (() => Promise<PreviewSource>)
  /** Read a row-limited archive split even when its first chunk exceeds the file preview limit. */
  datasetSplit?: boolean
  totalRows?: number
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
  isDownloading: boolean
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
  contentBlob?: Blob
  /** `contentBlob` is only the start of the file. */
  contentTruncated?: boolean
  parquetFile?: AsyncBuffer
  totalRows?: number
  fileName: string
}

export interface CodePreviewProps {
  textContent: string
  fileName: string
}
