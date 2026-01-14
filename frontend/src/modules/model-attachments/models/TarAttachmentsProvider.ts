import type {
  ModelAttachmentsProvider,
  AttachmentContent,
  FileNode,
} from '../interfaces/interfaces'

type FileIndex = Record<string, [number, number]>

interface ModelDownloader {
  url: string
  getFileFromBucket<T = unknown>(
    fileIndex: FileIndex,
    fileName: string,
    buffer?: boolean,
    outerOffset?: number,
  ): Promise<T>
}

export interface TarAttachmentsProviderConfig {
  downloader: ModelDownloader
  fileIndex: FileIndex
  findAttachmentsTarPath: (fileIndex: FileIndex) => string | undefined
  findAttachmentsIndexPath: (fileIndex: FileIndex) => string | undefined
}

export class TarAttachmentsProvider implements ModelAttachmentsProvider {
  private downloader: ModelDownloader
  private fileIndex: FileIndex
  private findAttachmentsTarPath: (fileIndex: FileIndex) => string | undefined
  private findAttachmentsIndexPath: (fileIndex: FileIndex) => string | undefined

  private tree: FileNode[] = []
  private tarBaseOffset: number = 0
  private attachmentsIndex: FileIndex = {}

  constructor(config: TarAttachmentsProviderConfig) {
    this.downloader = config.downloader
    this.fileIndex = config.fileIndex
    this.findAttachmentsTarPath = config.findAttachmentsTarPath
    this.findAttachmentsIndexPath = config.findAttachmentsIndexPath
  }

  async init(): Promise<void> {
    const indexPath = this.findAttachmentsIndexPath(this.fileIndex)
    if (!indexPath) {
      return
    }

    const indexData = await this.downloader.getFileFromBucket<FileIndex>(this.fileIndex, indexPath)

    const tarPath = this.findAttachmentsTarPath(this.fileIndex)
    if (!tarPath) {
      return
    }

    const tarRange = this.fileIndex[tarPath]
    if (!tarRange) {
      return
    }

    const [tarOffset] = tarRange
    this.tarBaseOffset = tarOffset
    this.attachmentsIndex = indexData
    this.tree = this.buildTreeFromIndex(indexData)
  }

  getTree(): FileNode[] {
    return this.tree
  }

  async getAttachmentContent(path: string): Promise<AttachmentContent> {
    const rangeData = this.attachmentsIndex[path]
    if (!rangeData) {
      throw new Error(`Attachment not found: ${path}`)
    }

    const [, size] = rangeData

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
    const root: Record<string, any> = {}

    const filePaths = Object.entries(index)
      .filter(([path, [, size]]) => size > 0 && !path.endsWith('/'))
      .map(([path]) => path)

    filePaths.forEach((fullPath) => {
      const path = fullPath.replace(/^attachments\//, '')
      const parts = path.split('/')
      const [, size] = index[fullPath]

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
              children: {},
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
