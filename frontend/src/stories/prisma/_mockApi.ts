import { api } from '@/lib/api'
import {
  mockAgents,
  mockBranches,
  mockBrowseResult,
  mockMergePreview,
  mockRepositories,
  mockTasks,
  mockRuns,
  mockNodes,
  mockEdges,
} from './_fixtures'

export interface PrismaApiOverrides {
  listAvailableAgents?: () => Promise<typeof mockAgents>
  listBranches?: (path: string) => Promise<string[]>
  browsePath?: (path?: string) => Promise<typeof mockBrowseResult>
  getMergePreview?: (id: string) => Promise<typeof mockMergePreview>
  getRunMergePreview?: (id: string) => Promise<typeof mockMergePreview>
  mergeTask?: (id: string) => Promise<{ status: string; message: string }>
  mergeRun?: (id: string) => Promise<{ status: string; message: string }>
  createRepository?: typeof api.dataAgent.createRepository
  createTask?: typeof api.dataAgent.createTask
  createRun?: typeof api.dataAgent.createRun
  listRepositories?: () => Promise<typeof mockRepositories>
  listTasks?: () => Promise<typeof mockTasks>
  listRuns?: () => Promise<typeof mockRuns>
  getBackendUrl?: () => string
  setBackendUrl?: (url: string) => void
}

const DEFAULTS: Required<PrismaApiOverrides> = {
  listAvailableAgents: async () => mockAgents,
  listBranches: async () => mockBranches,
  browsePath: async () => mockBrowseResult,
  getMergePreview: async () => mockMergePreview,
  getRunMergePreview: async () => mockMergePreview,
  mergeTask: async () => ({ status: 'ok', message: 'Merged' }),
  mergeRun: async () => ({ status: 'ok', message: 'Merged' }),
  createRepository: (async (body) => ({
    id: 'new-repo',
    name: body.name,
    path: body.path,
  })) as typeof api.dataAgent.createRepository,
  createTask: (async (body) => ({
    ...mockTasks[0],
    id: 'new-task',
    name: body.name,
    repository_id: body.repository_id,
    prompt: body.prompt,
    base_branch: body.base_branch,
    agent_id: body.agent_id,
  })) as typeof api.dataAgent.createTask,
  createRun: (async (body) => ({
    ...mockRuns[0],
    id: 'new-run',
    name: body.name,
    objective: body.objective,
    repository_id: body.repository_id,
  })) as typeof api.dataAgent.createRun,
  listRepositories: async () => mockRepositories,
  listTasks: async () => mockTasks,
  listRuns: async () => mockRuns,
  getBackendUrl: () => 'http://localhost:8420',
  setBackendUrl: () => undefined,
}

/**
 * Installs stubs on the shared `api.dataAgent` singleton. Safe to call from
 * decorators — later calls overwrite earlier ones.
 */
export function installPrismaApiStubs(overrides: PrismaApiOverrides = {}): void {
  const merged = { ...DEFAULTS, ...overrides }
  Object.assign(api.dataAgent, merged)
}

// Install defaults at module load so any Prisma story renders without errors
// even if it forgets to opt in.
installPrismaApiStubs()
