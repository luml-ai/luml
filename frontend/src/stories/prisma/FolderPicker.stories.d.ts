import type { Meta, StoryObj } from '@storybook/vue3';
import FolderPicker from '@/components/prisma/FolderPicker.vue';
import './_mockApi';
declare const meta: Meta<typeof FolderPicker>;
export default meta;
type Story = StoryObj<typeof meta>;
export declare const Empty: Story;
export declare const PreSelected: Story;
