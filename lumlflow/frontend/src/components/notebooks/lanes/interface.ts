export type NotebookLaneState = 'active' | 'inactive'

export interface INotebookLane {
  id: string
  name: string
  stepsLabel: string | null
  updatedAgo: string
  parentId: string | null
  state: NotebookLaneState
  current?: boolean
}

export interface INotebookLaneNode extends INotebookLane {
  children: INotebookLaneNode[]
}
