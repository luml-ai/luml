import NewItemDialog from '@/components/prisma/NewItemDialog.vue';
import { mockRepositories } from './_fixtures';
import './_mockApi';
const meta = {
    title: 'Prisma/NewItemDialog',
    component: NewItemDialog,
    tags: ['autodocs'],
    parameters: {
        layout: 'fullscreen',
        docs: {
            description: {
                component: 'Modal to create a new task or workflow. The SelectButton at the top toggles between TaskForm and WorkflowForm; the default is Workflow.',
            },
        },
    },
    argTypes: {
        initialType: { control: 'select', options: ['task', 'workflow'] },
    },
};
export default meta;
export const WorkflowFirst = {
    args: {
        visible: true,
        initialType: 'workflow',
        repositories: mockRepositories,
    },
    parameters: {
        docs: {
            description: {
                story: 'Default entry point — Workflow tab is selected first.',
            },
        },
    },
};
export const TaskTab = {
    args: {
        visible: true,
        initialType: 'task',
        repositories: mockRepositories,
    },
};
export const NoRepositories = {
    args: {
        visible: true,
        initialType: 'workflow',
        repositories: [],
    },
};
