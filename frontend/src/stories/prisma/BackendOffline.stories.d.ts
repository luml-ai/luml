import type { Meta, StoryObj } from '@storybook/vue3';
import BackendOffline from '@/components/prisma/BackendOffline.vue';
import './_mockApi';
declare const meta: Meta<typeof BackendOffline>;
export default meta;
type Story = StoryObj<typeof meta>;
export declare const EngineOffline: Story;
export declare const VersionMismatch: Story;
