import MergeDialog from '@/components/prisma/MergeDialog.vue';
import { mockMergePreview, mockMergePreviewConflict } from './_fixtures';
import { installPrismaApiStubs } from './_mockApi';
const meta = {
    title: 'Prisma/MergeDialog',
    component: MergeDialog,
    tags: ['autodocs'],
    parameters: {
        layout: 'fullscreen',
        docs: {
            description: {
                component: "Merge preview modal — shown when the user clicks Merge on a task or on a workflow's best branch. Fetches a preview from the backend and lets the user confirm.",
            },
        },
    },
    argTypes: {
        kind: { control: 'select', options: ['task', 'run'] },
    },
};
export default meta;
export const TaskMerge = {
    args: { visible: true, kind: 'task', itemId: 'task-succeeded' },
    play: async () => {
        installPrismaApiStubs({
            getMergePreview: async () => mockMergePreview,
        });
    },
};
export const WorkflowMerge = {
    args: { visible: true, kind: 'run', itemId: 'run-succeeded' },
    play: async () => {
        installPrismaApiStubs({
            getRunMergePreview: async () => ({
                ...mockMergePreview,
                branch: 'prisma/run-best',
            }),
        });
    },
};
export const NotFastForward = {
    args: { visible: true, kind: 'task', itemId: 'task-succeeded' },
    play: async () => {
        installPrismaApiStubs({
            getMergePreview: async () => mockMergePreviewConflict,
        });
    },
    parameters: {
        docs: {
            description: {
                story: 'Preview with `can_fast_forward = false` — the green fast-forward hint is hidden.',
            },
        },
    },
};
export const LoadFailure = {
    args: { visible: true, kind: 'task', itemId: 'task-succeeded' },
    play: async () => {
        installPrismaApiStubs({
            getMergePreview: async () => {
                throw { response: { data: { detail: 'Could not compute merge preview' } } };
            },
        });
    },
};
