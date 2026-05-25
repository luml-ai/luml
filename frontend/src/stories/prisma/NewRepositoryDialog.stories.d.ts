import type { Meta, StoryObj } from '@storybook/vue3';
import NewRepositoryDialog from '@/components/prisma/NewRepositoryDialog.vue';
import './_mockApi';
declare const meta: Meta<typeof NewRepositoryDialog>;
export default meta;
type Story = StoryObj<typeof meta>;
export declare const Open: Story;
