import type { Meta, StoryObj } from '@storybook/vue3';
import BackendIndicator from '@/components/prisma/BackendIndicator.vue';
declare const meta: Meta<typeof BackendIndicator>;
export default meta;
type Story = StoryObj<typeof meta>;
export declare const Localhost: Story;
export declare const RemoteHost: Story;
