import BackendOffline from '@/components/prisma/BackendOffline.vue';
import './_mockApi';
const meta = {
    title: 'Prisma/BackendOffline',
    component: BackendOffline,
    tags: ['autodocs'],
    parameters: {
        layout: 'fullscreen',
        docs: {
            description: {
                component: 'Full-page state shown when the Prisma engine is unreachable (or reports an incompatible version). Offers install / run commands and a URL entry field with a Connect button.',
            },
        },
    },
};
export default meta;
export const EngineOffline = {
    args: { versionMismatch: false },
    parameters: {
        docs: {
            description: { story: 'Default offline state — engine is unreachable.' },
        },
    },
};
export const VersionMismatch = {
    args: { versionMismatch: true },
    parameters: {
        docs: {
            description: {
                story: 'Engine responded but the version does not match the frontend.',
            },
        },
    },
};
