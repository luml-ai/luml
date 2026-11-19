export const FILE_TYPES = {
  image: ['png', 'jpg', 'jpeg', 'gif', 'webp'],
  svg: ['svg'],
  audio: ['mp3', 'wav', 'ogg'],
  video: ['mp4', 'webm', 'ogv'],
  text: ['txt', 'md', 'json', 'log'],
  code: ['py', 'js', 'ts', 'yaml', 'yml', 'toml', 'ini', 'cfg', 'sh', 'sql', 'jsx', 'tsx', 'css'],
  table: ['csv', 'xml', 'parquet', 'arrow'],
  pdf: ['pdf'],
  html: ['html'],
} as const

export type FileType = keyof typeof FILE_TYPES
export type FileExtension = (typeof FILE_TYPES)[FileType][number]

export const EXTENSION_LANGUAGES = {
  py: 'python',
  js: 'javascript',
  jsx: 'jsx',
  ts: 'typescript',
  tsx: 'tsx',
  json: 'json',
  yaml: 'yaml',
  yml: 'yaml',
  md: 'markdown',
  css: 'css',
  sql: 'sql',
  xml: 'xml',
  html: 'html',
} as const satisfies Partial<Record<FileExtension, string>>

export type PreviewLanguage = (typeof EXTENSION_LANGUAGES)[keyof typeof EXTENSION_LANGUAGES]

export function getPreviewLanguage(filename: string): PreviewLanguage | undefined {
  const extension = getFileExtension(filename)
  if (Object.prototype.hasOwnProperty.call(EXTENSION_LANGUAGES, extension)) {
    return EXTENSION_LANGUAGES[extension as keyof typeof EXTENSION_LANGUAGES]
  }
}

export function getFileExtension(filename: string): string {
  if (!filename) return ''
  const basename = filename.slice(
    Math.max(filename.lastIndexOf('/'), filename.lastIndexOf('\\')) + 1,
  )
  const dot = basename.lastIndexOf('.')
  return dot > 0 ? basename.slice(dot + 1).toLowerCase() : ''
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
