export type NotebookAssetType = 'graph' | 'model' | 'dataset' | 'experiment' | 'unknown'

export interface NotebookAssetInterface {
  id: string
  type: NotebookAssetType
  name: string
  unmaterialized: boolean
}
