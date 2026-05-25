import type { Meta, StoryObj } from '@storybook/vue3';
import NewItemDialog from '@/components/prisma/NewItemDialog.vue';
import './_mockApi';
declare const meta: Meta<typeof NewItemDialog>;
export default meta;
type Story = StoryObj<typeof meta>;
export declare const WorkflowFirst: Story;
export declare const TaskTab: Story;
export declare const NoRepositories: Story;
