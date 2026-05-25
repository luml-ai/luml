import type { Meta, StoryObj } from '@storybook/vue3';
import WorkflowForm from '@/components/prisma/WorkflowForm.vue';
import './_mockApi';
declare const meta: Meta<typeof WorkflowForm>;
export default meta;
type Story = StoryObj<typeof meta>;
export declare const Default: Story;
export declare const Loading: Story;
export declare const NoRepositories: Story;
