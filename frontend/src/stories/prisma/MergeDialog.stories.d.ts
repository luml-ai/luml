import type { Meta, StoryObj } from '@storybook/vue3';
import MergeDialog from '@/components/prisma/MergeDialog.vue';
declare const meta: Meta<typeof MergeDialog>;
export default meta;
type Story = StoryObj<typeof meta>;
export declare const TaskMerge: Story;
export declare const WorkflowMerge: Story;
export declare const NotFastForward: Story;
export declare const LoadFailure: Story;
