export interface IWorkspaceFolderItem {
  id: string
  name: string
  entryName?: string
  type: 'folder' | 'file' | 'flow'
  path: string
  size: number | null
  is_symlink?: boolean
  modified_at?: string | null
}
