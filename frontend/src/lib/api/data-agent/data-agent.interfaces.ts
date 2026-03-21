export interface AgentRepository {
  id: string
  name: string
  path: string
}

export interface AgentTask {
  id: string
  repository_id: string
  name: string
  branch: string
  worktree_path: string
  agent_id: string
  status: string
  prompt: string
  base_branch: string
  position?: number | null
  created_at: string
  updated_at: string
  is_alive?: boolean
  session_id?: string
  has_waiting_input?: boolean
}

export interface Agent {
  id: string
  name: string
  cli: string
  prompt_flag: string
  auto_approve_flag: string
  resume_flag: string
  default_args: string[]
}

export interface BranchDiffStats {
  commits_ahead: number
  files_changed: number
  insertions: number
  deletions: number
}

export interface MergePreview {
  branch: string
  base_branch: string
  stats: BranchDiffStats
  commit_messages: string[]
  changed_files: string[]
  can_fast_forward: boolean
}

export interface BrowseEntry {
  name: string
  path: string
  is_git: boolean
}

export interface BrowseResult {
  current: string
  parent: string | null
  dirs: BrowseEntry[]
  is_git: boolean
}

export interface RepositoryCreate {
  name: string
  path: string
}

export interface TaskCreate {
  repository_id: string
  name: string
  agent_id: string
  prompt: string
  base_branch: string
}

export interface RunConfig {
  max_depth: number
  max_children_per_fork: number
  max_debug_retries: number
  max_concurrency: number
  run_command_template: string
  agent_id: string
  fork_auto_approve: boolean
  auto_mode: boolean
  auto_terminate_timeout: number
}

export interface Run {
  id: string
  repository_id: string
  name: string
  objective: string
  status: string
  config: RunConfig
  base_branch: string
  best_node_id?: string | null
  position?: number | null
  created_at: string
  updated_at: string
  has_waiting_input?: boolean
}

export interface RunNode {
  id: string
  run_id: string
  parent_node_id: string | null
  node_type: string
  status: string
  depth: number
  payload: Record<string, any>
  result: Record<string, any>
  worktree_path: string
  branch: string
  debug_retries: number
  created_at: string
  updated_at: string
  session_id?: string | null
  is_alive?: boolean
}

export interface RunEdge {
  id: string
  run_id: string
  from_node_id: string
  to_node_id: string
  reason: string
}

export interface RunEvent {
  seq: number
  type: string
  node_id: string | null
  data: Record<string, any>
}

export interface RunGraph {
  nodes: RunNode[]
  edges: RunEdge[]
}

export interface RunCreate {
  repository_id: string
  name: string
  objective: string
  base_branch?: string
  agent_id?: string
  run_command?: string
  max_depth?: number
  max_children_per_fork?: number
  max_debug_retries?: number
  max_concurrency?: number
  fork_auto_approve?: boolean
  auto_mode?: boolean
  auto_terminate_timeout?: number
}
