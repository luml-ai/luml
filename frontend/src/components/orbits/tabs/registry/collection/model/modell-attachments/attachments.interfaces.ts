import type { Component, Ref } from 'vue'

export interface FileNode {
  name: string
  path?: string
  type: 'file' | 'folder'
  size?: number
  children?: FileNode[]
}

export interface FileContentResult {
  blob?: Blob
  text?: string
  contentUrl?: string
  error?: 'empty' | 'too-big' | 'not-found' | 'unsupported' | 'unknown'
}

export type PreviewState = 'loading' | 'error' | 'unsupported' | 'too-big' | 'empty' | null

export interface FetchFileContentParams {
  file: FileNode
  fileIndex: Record<string, [number, number]>
  downloadUrl: string
}

export interface UseFilePreviewProps {
  file: Ref<FileNode | null>
  fileIndex: Ref<Record<string, [number, number]>>
  modelId: Ref<string>
  getDownloadUrl: (modelId: string) => Promise<string>
}

export interface FilePreviewState {
  isLoading: Ref<boolean>
  error: Ref<string | null>
  contentUrl: Ref<string>
  textContent: Ref<string>
  contentBlob: Ref<Blob | null>
}

export interface FileNodeProps {
  node: FileNode
  selected: FileNode | null
}

export interface FileNodeEmits {
  (e: 'select', node: FileNode): void
}

export type FileIconMap = Record<string, Component>

export interface SvgPreviewProps {
  contentUrl: string
  fileName: string
}

export interface PdfPreviewProps {
  contentUrl: string
}

export interface ImagePreviewProps {
  contentUrl: string
  fileName: string
}

export interface CodePreviewProps {
  textContent: string
  fileName?: string
}

export interface FilePreviewHeaderProps {
  fileName: string
  fileSize?: number
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

export interface MediaPreviewProps {
  type: 'audio' | 'video'
  contentUrl: string
}

export interface HtmlPreviewProps {
  contentUrl: string
}

export interface TablePreviewProps {
  contentBlob: Blob
  fileName: string
}
