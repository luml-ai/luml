import NewRepositoryDialog from '@/components/prisma/NewRepositoryDialog.vue';
import './_mockApi';
const meta = {
    title: 'Prisma/NewRepositoryDialog',
    component: NewRepositoryDialog,
    tags: ['autodocs'],
    parameters: {
        layout: 'fullscreen',
        docs: {
            description: {
                component: 'Modal to register a new repository. Name + FolderPicker (which drives `api.dataAgent.browsePath`).',
            },
        },
    },
};
export default meta;
export const Open = {
    args: { visible: true },
};
