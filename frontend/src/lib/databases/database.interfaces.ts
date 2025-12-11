export interface DatabaseMetadata {
  createdAt: number
  fullname: string
}

type FileFormats = 'json'
type FileTypes = '"notebook"'

export interface LumlFile {
  content: any
  created: Date
  format: FileFormats
  last_modified: Date
  mimetype: any
  name: string
  path: string
  size: number
  type: FileTypes
  writable: boolean
}

export interface Notebook extends Partial<DatabaseMetadata> {
  name: string
  version: number
  files?: LumlFile[]
}
