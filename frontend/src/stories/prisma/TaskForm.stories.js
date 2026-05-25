import TaskForm from '@/components/prisma/TaskForm.vue';
import { mockRepositories } from './_fixtures';
import { installPrismaApiStubs } from './_mockApi';
const meta = {
    title: 'Prisma/TaskForm',
    component: TaskForm,
    tags: ['autodocs'],
    parameters: {
        layout: 'padded',
        docs: {
            description: {
                component: 'Form used inside the New Item dialog when creating a one-shot task. Loads available agents via `api.dataAgent.listAvailableAgents()` and branch options via `api.dataAgent.listBranches(repoPath)` when a repository is selected.',
            },
        },
    },
    decorators: [
        (story) => ({
            components: { story },
            template: '<div style="width: 480px;"><story /></div>',
        }),
    ],
};
export default meta;
export const Default = {
    args: { repositories: mockRepositories, loading: false },
};
export const Loading = {
    args: { repositories: mockRepositories, loading: true },
};
export const NoRepositories = {
    args: { repositories: [], loading: false },
};
export const BranchFetchSlow = {
    args: { repositories: mockRepositories, loading: false },
    play: async () => {
        installPrismaApiStubs({
            listBranches: async () => {
                await new Promise((r) => setTimeout(r, 2000));
                return ['main', 'develop'];
            },
        });
    },
    parameters: {
        docs: {
            description: {
                story: 'Simulates a slow `listBranches` call — the base branch Select shows its loading state for ~2s after selecting a repository.',
            },
        },
    },
};
