import type { Meta, StoryObj } from '@storybook/vue3'
import GraphNodeCard from '@/components/prisma/GraphNodeCard.vue'
import { mockNodes } from './_fixtures'
import './_mockApi'

const meta: Meta<typeof GraphNodeCard> = {
  title: 'Prisma/GraphNodeCard',
  component: GraphNodeCard,
  tags: ['autodocs'],
  parameters: {
    layout: 'centered',
    docs: {
      description: {
        component:
          'Node card rendered inside the Prisma run graph (VueFlow). Shows node type, status dot/label, a score for `run` nodes, a `best` badge, and a terminal icon when a session is attached.',
      },
    },
  },
  decorators: [
    (story) => ({
      components: { story },
      template: '<div style="padding: 24px;"><story /></div>',
    }),
  ],
}

export default meta
type Story = StoryObj<typeof meta>

const implement = mockNodes.find((n) => n.id === 'node-impl-1')!
const runSucceeded = mockNodes.find((n) => n.id === 'node-run-2')!
const runRunning = mockNodes.find((n) => n.id === 'node-run-running')!
const waiting = mockNodes.find((n) => n.id === 'node-waiting')!
const failed = mockNodes.find((n) => n.id === 'node-failed')!

export const ImplementSucceeded: Story = {
  args: { data: implement, selected: false },
}

export const RunSucceeded: Story = {
  args: { data: { ...runSucceeded }, selected: false },
  parameters: {
    docs: {
      description: {
        story: 'Run node with a numeric score pulled from `result.artifacts.metric`.',
      },
    },
  },
}

export const RunBest: Story = {
  args: { data: { ...runSucceeded, isBest: true }, selected: true },
  parameters: {
    docs: {
      description: {
        story: 'Best node is highlighted with a green tint on the score pill and a `best` badge.',
      },
    },
  },
}

export const Running: Story = {
  args: {
    data: {
      ...runRunning,
      onOpenTerminal: (id) => console.log('open terminal', id),
    },
    selected: false,
  },
  parameters: {
    docs: {
      description: {
        story:
          'Running node shows a terminal icon in the header. Clicking it fires `onOpenTerminal(sessionId)`.',
      },
    },
  },
}

export const WaitingInput: Story = {
  args: {
    data: {
      ...waiting,
      onOpenTerminal: (id) => console.log('open terminal', id),
    },
    selected: false,
  },
}

export const Failed: Story = {
  args: { data: failed, selected: false },
}
