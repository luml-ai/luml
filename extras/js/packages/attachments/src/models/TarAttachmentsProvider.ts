import type {
  ModelAttachmentsProvider,
  AttachmentContent,
  FileNode,
} from '../interfaces/interfaces'
import { getFileExtension, getFileType } from '../utils/fileTypes'
import { createPreviewStreamUrl } from '../utils/previewStream'

type FileIndex = Record<string, [number, number]>

interface ModelDownloader {
  readRange?(start: number, end: number): Promise<ArrayBuffer>
  getFileFromBucket<T = unknown>(
    fileIndex: FileIndex,
    fileName: string,
    buffer?: boolean,
    outerOffset?: number,
  ): Promise<T>
}

export interface TarAttachmentsProviderConfig {
  downloader: ModelDownloader
  previewWorkerUrl?: string
  fileIndex: FileIndex
  attachmentsIndex?: FileIndex
  findAttachmentsTarPath: (fileIndex: FileIndex) => string | undefined
  findAttachmentsIndexPath: (fileIndex: FileIndex) => string | undefined
}

export class TarAttachmentsProvider implements ModelAttachmentsProvider {
  private downloader: ModelDownloader
  private previewWorkerUrl?: string
  private fileIndex: FileIndex
  private findAttachmentsTarPath: (fileIndex: FileIndex) => string | undefined
  private findAttachmentsIndexPath: (fileIndex: FileIndex) => string | undefined
  private initialAttachmentsIndex?: FileIndex

  private tree: FileNode[] = []
  private tarBaseOffset: number = 0
  private tarSize = 0
  private attachmentsIndex: FileIndex = {}

  constructor(config: TarAttachmentsProviderConfig) {
    this.downloader = config.downloader
    this.previewWorkerUrl = config.previewWorkerUrl
    this.fileIndex = config.fileIndex
    this.findAttachmentsTarPath = config.findAttachmentsTarPath
    this.findAttachmentsIndexPath = config.findAttachmentsIndexPath
    this.initialAttachmentsIndex = config.attachmentsIndex
  }

  async init(): Promise<void> {
    const indexPath = this.findAttachmentsIndexPath(this.fileIndex)
    if (!indexPath) {
      return
    }

    const indexData =
      this.initialAttachmentsIndex ??
      (await this.downloader.getFileFromBucket<FileIndex>(this.fileIndex, indexPath))

    const tarPath = this.findAttachmentsTarPath(this.fileIndex)
    if (!tarPath) {
      return
    }

    const tarRange = this.fileIndex[tarPath]
    if (!tarRange) {
      return
    }

    this.tarBaseOffset = tarRange[0]
    this.tarSize = tarRange[1]
    this.attachmentsIndex = indexData
    this.tree = this.buildTreeFromIndex(indexData)
  }

  getTree(): FileNode[] {
    return this.tree
  }

  private getRange(path: string): [number, number] {
    if (!Object.prototype.hasOwnProperty.call(this.attachmentsIndex, path)) {
      throw new Error(`Attachment not found: ${path}`)
    }
    const range = this.attachmentsIndex[path]!
    const [offset, size] = range
    const base = this.tarBaseOffset + offset
    if (
      ![this.tarBaseOffset, this.tarSize, offset, size, base + size].every(Number.isSafeInteger) ||
      this.tarBaseOffset < 0 ||
      offset < 0 ||
      size < 0 ||
      offset + size > this.tarSize
    ) {
      throw new Error('Invalid attachment range')
    }
    return range
  }

  supportsPartialPreview(path: string) {
    if (getFileExtension(path) === 'parquet') return true
    const type = getFileType(path)
    return Boolean(
      this.previewWorkerUrl &&
      navigator.serviceWorker &&
      (type === 'audio' || type === 'video' || type === 'pdf'),
    )
  }

  async getPreviewSource(path: string) {
    const type = getFileType(path)
    const workerUrl =
      this.supportsPartialPreview(path) && type !== 'table' ? this.previewWorkerUrl : undefined
    if (!workerUrl && getFileExtension(path) !== 'parquet') {
      return (await this.getAttachmentContent(path)).blob
    }
    const [offset, size] = this.getRange(path)
    const source = {
      byteLength: size,
      slice: async (start: number, end = size) => {
        if (
          !Number.isSafeInteger(start) ||
          !Number.isSafeInteger(end) ||
          start < 0 ||
          start > end ||
          end > size
        ) {
          throw new RangeError('Invalid attachment slice')
        }
        if (start === end) return new ArrayBuffer(0)
        const base = this.tarBaseOffset + offset
        const bytes = this.downloader.readRange
          ? await this.downloader.readRange(base + start, base + end)
          : await this.downloader.getFileFromBucket<ArrayBuffer>(
              { [path]: [offset + start, end - start] },
              path,
              true,
              this.tarBaseOffset,
            )
        if (bytes.byteLength !== end - start) throw new Error('Incomplete attachment range')
        return bytes
      },
    }
    return workerUrl ? createPreviewStreamUrl(path, source, workerUrl) : source
  }

  async getAttachmentContent(path: string): Promise<AttachmentContent> {
    const [, size] = this.getRange(path)

    if (size === 0) {
      throw new Error(`Attachment is empty: ${path}`)
    }

    const arrayBuffer = await this.downloader.getFileFromBucket<ArrayBuffer>(
      this.attachmentsIndex,
      path,
      true,
      this.tarBaseOffset,
    )

    return {
      blob: new Blob([arrayBuffer]),
      size,
    }
  }

  isEmpty(): boolean {
    return this.tree.length === 0
  }

  private buildTreeFromIndex(index: FileIndex): FileNode[] {
    const root: Record<string, any> = Object.create(null)

    const filePaths = Object.entries(index)
      .filter(([path, [, size]]) => size > 0 && !path.endsWith('/'))
      .map(([path]) => path)

    filePaths.forEach((fullPath) => {
      const path = fullPath.replace(/^attachments\//, '')
      const parts = path.split('/')

      const size = index[fullPath]?.[1] || 0

      let current = root

      parts.forEach((part, idx) => {
        if (idx === parts.length - 1) {
          current[part] = {
            type: 'file',
            path: fullPath,
            size,
          }
        } else {
          if (!current[part]) {
            current[part] = {
              type: 'folder',
              children: Object.create(null),
            }
          }
          current = current[part].children
        }
      })
    })

    return this.convertToArray(root)
  }

  private convertToArray(obj: Record<string, any>): FileNode[] {
    return Object.entries(obj).map(([name, data]: [string, any]) => {
      if (data.type === 'file') {
        return {
          name,
          path: data.path,
          type: 'file' as const,
          size: data.size,
        }
      } else {
        return {
          name,
          type: 'folder' as const,
          children: this.convertToArray(data.children),
        }
      }
    })
  }
}
