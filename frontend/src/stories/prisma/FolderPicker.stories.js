import { ref } from 'vue';
import FolderPicker from '@/components/prisma/FolderPicker.vue';
import './_mockApi';
const meta = {
    title: 'Prisma/FolderPicker',
    component: FolderPicker,
    tags: ['autodocs'],
    parameters: {
        layout: 'centered',
        docs: {
            description: {
                component: 'Path input with a server-backed folder browser. Directories marked with a Git icon can be selected directly; the parent of the current directory is always clickable.',
            },
        },
    },
    decorators: [
        (story) => ({
            components: { story },
            template: '<div style="width: 440px;"><story /></div>',
        }),
    ],
};
export default meta;
export const Empty = {
    render: () => ({
        components: { FolderPicker },
        setup() {
            const path = ref('');
            return { path };
        },
        template: '<FolderPicker v-model="path" />',
    }),
};
export const PreSelected = {
    render: () => ({
        components: { FolderPicker },
        setup() {
            const path = ref('/home/user/dev/ml-experiments');
            return { path };
        },
        template: '<FolderPicker v-model="path" />',
    }),
};
