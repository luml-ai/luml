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
