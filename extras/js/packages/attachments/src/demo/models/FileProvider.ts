import type { AttachmentContent, FileNode, ModelAttachmentsProvider } from '@/interfaces/interfaces'

export class FileProvider implements ModelAttachmentsProvider {
  private tree: FileNode[] = []
  private fileIndex: Record<string, [number, number]>

  constructor(
    private index: Uint8Array,
    private tar: Uint8Array,
  ) {
    this.fileIndex = JSON.parse(new TextDecoder().decode(this.index))
    this.buildTree()
  }

  getTree(): FileNode[] {
    return this.tree
  }

  async getAttachmentContent(path: string): Promise<AttachmentContent> {
    const rangeData = this.fileIndex[path]
    if (!rangeData) {
      throw new Error(`Attachment not found: ${path}`)
    }

    const [, size] = rangeData

    if (size === 0) {
      throw new Error(`Attachment is empty: ${path}`)
    }

    const arrayBuffer = this.tar.subarray(rangeData[0], rangeData[0] + size)

    return {
      blob: new Blob([new Uint8Array(arrayBuffer)]),
      size,
    }
  }

  isEmpty(): boolean {
    return this.tree.length === 0
  }

  private buildTree() {
    const root: Record<string, any> = {}

    const filePaths = Object.entries(this.fileIndex)
      .filter(([path, [, size]]) => size > 0 && !path.endsWith('/'))
      .map(([path]) => path)

    filePaths.forEach((fullPath) => {
      const path = fullPath.replace(/^attachments\//, '')
      const parts = path.split('/')

      const size = this.fileIndex[fullPath]?.[1] || 0

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

    this.tree = this.convertToArray(root)
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
