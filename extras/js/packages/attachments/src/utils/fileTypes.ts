export const FILE_TYPES = {
  image: ['png', 'jpg', 'jpeg'],
  svg: ['svg'],
  audio: ['mp3', 'wav', 'ogg'],
  video: ['mp4', 'webm', 'ogv'],
  text: ['txt', 'md', 'json'],
  code: ['py', 'js', 'ts', 'yaml', 'yml'],
  table: ['csv', 'xml'],
  pdf: ['pdf'],
  html: ['html'],
} as const

export type FileType = keyof typeof FILE_TYPES
export type FileExtension = (typeof FILE_TYPES)[FileType][number]

export function getFileExtension(filename: string): string {
  if (!filename) return ''
  return filename.split('.').pop()?.toLowerCase() || ''
}

export function getFileType(filename: string): FileType | null {
  const ext = getFileExtension(filename)
  for (const [type, extensions] of Object.entries(FILE_TYPES)) {
    if ((extensions as readonly string[]).includes(ext)) {
      return type as FileType
    }
  }
  return null
}

export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}
