export interface WorkspaceFlow {
  name: string
  path: string
  relative_path: string
}

export interface WorkspaceListing {
  directory: string
  flows: WorkspaceFlow[]
}

export interface CreatedFlow {
  flow: string
  path: string
  warnings: string[]
}

export interface RenamedFlow {
  renamed: string
  path: string
  from: string
}

export interface DeletedFlow {
  deleted: string
  path: string
}

export interface DuplicatedFlow {
  flow: string
  path: string
}

export interface BranchLastIntent {
  ts: string
  step: number
}

export interface BranchRecord {
  branch: string
  parent: string | null
  forked_at_step: number
  parent_step: number | null
  archived: boolean
  checked_out: boolean
  cells: number
  last_intent: BranchLastIntent | null
}

export interface BranchTree {
  flow: string
  branch: string
  branches: BranchRecord[]
}

export interface SwitchedBranch {
  branch: string
}

export interface ForkedBranch {
  branch: string
  from_branch: string
}
