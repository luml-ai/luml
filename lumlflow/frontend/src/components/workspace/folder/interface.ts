export interface IWorkspaceFolderItem {
  id: string
  name: string
  type: 'folder' | 'file' | 'flow'
  path: string
  size: number
}
