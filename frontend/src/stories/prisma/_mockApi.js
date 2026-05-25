import { api } from '@/lib/api';
import { mockAgents, mockBranches, mockBrowseResult, mockMergePreview, mockRepositories, mockTasks, mockRuns, } from './_fixtures';
const DEFAULTS = {
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
    })),
    createTask: (async (body) => ({
        ...mockTasks[0],
        id: 'new-task',
        name: body.name,
        repository_id: body.repository_id,
        prompt: body.prompt,
        base_branch: body.base_branch,
        agent_id: body.agent_id,
    })),
    createRun: (async (body) => ({
        ...mockRuns[0],
        id: 'new-run',
        name: body.name,
        objective: body.objective,
        repository_id: body.repository_id,
    })),
    listRepositories: async () => mockRepositories,
    listTasks: async () => mockTasks,
    listRuns: async () => mockRuns,
    getBackendUrl: () => 'http://localhost:8420',
    setBackendUrl: () => undefined,
};
/**
 * Installs stubs on the shared `api.dataAgent` singleton. Safe to call from
 * decorators — later calls overwrite earlier ones.
 */
export function installPrismaApiStubs(overrides = {}) {
    const merged = { ...DEFAULTS, ...overrides };
    Object.assign(api.dataAgent, merged);
}
// Install defaults at module load so any Prisma story renders without errors
// even if it forgets to opt in.
installPrismaApiStubs();
