export type NotebookLaneState = 'active' | 'inactive'

export interface INotebookLane {
  id: string
  name: string
  steps: number
  updatedAgo: string
  parentId: string | null
  state: NotebookLaneState
  /** The lane checked out right now — its row gets the tinted background and its
   * name renders as the active link. */
  current?: boolean
}

export interface INotebookLaneNode extends INotebookLane {
  children: INotebookLaneNode[]
}
