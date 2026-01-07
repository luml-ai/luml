import type { Meta, StoryObj } from '@storybook/vue3'
import ExperimentSnapshot from '@/modules/experiment-snapshot/ExperimentSnapshot.vue'
import type {
  ExperimentSnapshotProvider,
  ExperimentSnapshotStaticParams,
  ExperimentSnapshotDynamicMetrics,
  ModelsInfo,
  EvalsInfo,
  SpansParams,
} from '@/modules/experiment-snapshot/interfaces/interfaces'
import { Toast } from 'primevue'
import StorybookPageWrapper from './StorybookPageWrapper.vue'

const createMockProvider = (
  options: {
    staticParams?: ExperimentSnapshotStaticParams[]
    dynamicMetrics?: ExperimentSnapshotDynamicMetrics
    evalsList?: Record<string, EvalsInfo[]> | null
    shouldError?: boolean
    delay?: number
  } = {},
): ExperimentSnapshotProvider => {
  const {
    staticParams = [
      {
        modelId: 'model-1',
        eval_dataset: 'test-dataset-v1',
        eval_version: '1.0.0',
        evaluation_metrics: ['metric_0', 'metric_1', 'metric_2'],
        model_type: 'gpt-4',
      },
    ],
    dynamicMetrics = {
      metric_0: {
        x: [
          0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24,
          25, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47,
          48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60,
        ],
        y: [
          0.8995359313058078, 0.8921633542579104, 0.919900524147073, 0.9068530592605596,
          0.9342341324669194, 0.912370859332579, 0.9442305125810012, 0.9198631243793877,
          0.896257931591531, 0.9058574857800854, 0.9364271549290377, 0.8705695750799245,
          0.8923569434557828, 0.901293040857807, 0.8729544664818389, 0.9110427949914617,
          0.9091526770199423, 0.9087236594166883, 0.8921476141082693, 0.9412295897249782,
          0.9239474743574301, 0.907737080756125, 0.9066333431895796, 0.8752670234761472,
          0.8861950047650623, 0.8989245627245482, 0.8928156391966117, 0.9154425131162904,
          0.9340915958303736, 0.8996133453042163, 0.9180105306609642, 0.8963485287077425,
          0.873300571778433, 0.9071532318377863, 0.8803786247537504, 0.8947352125402608,
          0.9092842955833303, 0.8775214935796677, 0.8992256072813541, 0.9063718909478086,
          0.8812000110344826, 0.887042441256244, 0.9068893794252318, 0.8883335426082796,
          0.8837827208457694, 0.9034094250372017, 0.8851678999481599, 0.8406559543705853,
          0.8982231459619929, 0.8964164494876314, 0.9427851347647453, 0.8947752601291242,
          0.8672347679950712, 0.9201312695311938, 0.9010632389762617, 0.8756972769221129,
          0.8802466516605558, 0.8548386782078314, 0.8443020359311175, 0.8709284432292211,
          0.8467280864500022,
        ],
        modelId: 'model-1',
        aggregated: false,
      },
      metric_2: {
        x: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        y: [0.62, 0.69, 0.75, 0.79, 0.82, 0.84, 0.86, 0.88, 0.89, 0.9],
        modelId: 'model-1',
        aggregated: false,
      },
      metric_3: {
        x: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        y: [150, 145, 140, 135, 130, 128, 125, 123, 120, 118],
        modelId: 'model-1',
        aggregated: false,
      },
    },
    evalsList = {
      'dataset-1': [
        {
          id: 'eval-1',
          dataset_id: 'dataset-1',
          inputs: {
            prompt: 'What is the capital of France?',
            context: 'Geography question',
            temperature: 0.7,
          },
          outputs: {
            response: 'The capital of France is Paris.',
            tokens_used: 45,
          },
          refs: {
            expected: 'Paris',
            category: 'geography',
          },
          scores: {
            metric_0: 1.0,
            coherence: 0.95,
            relevance: 0.98,
          },
          metadata: {
            timestamp: Date.now() - 3600000,
            model_version: 1,
            duration_ms: 1250,
          },
          modelId: 'model-1',
        },
        {
          id: 'eval-2',
          dataset_id: 'dataset-1',
          inputs: {
            prompt: 'Explain quantum computing in simple terms',
            context: 'Technical question',
            temperature: 0.5,
          },
          outputs: {
            response:
              'Quantum computing uses quantum mechanics principles like superposition and entanglement to process information in ways that classical computers cannot. Instead of traditional bits (0 or 1), quantum computers use qubits which can exist in multiple states simultaneously.',
            tokens_used: 156,
          },
          refs: {
            expected: 'A clear, accessible explanation of quantum computing',
            category: 'science',
          },
          scores: {
            metric_0: 0.88,
            coherence: 0.92,
            completeness: 0.85,
            simplicity: 0.9,
          },
          metadata: {
            timestamp: Date.now() - 7200000,
            model_version: 1,
            duration_ms: 2100,
          },
          modelId: 'model-1',
        },
        {
          id: 'eval-3',
          dataset_id: 'dataset-1',
          inputs: {
            prompt: 'Write a haiku about spring',
            context: 'Creative writing',
            temperature: 0.9,
          },
          outputs: {
            response: 'Cherry blossoms fall\nGentle breeze carries petals\nSpring awakens life',
            tokens_used: 28,
          },
          refs: {
            expected: 'A haiku with spring theme, 5-7-5 syllable structure',
            category: 'creative',
          },
          scores: {
            metric_0: 0.95,
            creativity: 0.97,
            structure: 1.0,
            imagery: 0.94,
          },
          metadata: {
            timestamp: Date.now() - 10800000,
            model_version: 1,
            duration_ms: 980,
          },
          modelId: 'model-1',
        },
      ],
    },
    shouldError = false,
    delay = 0,
  } = options

  return {
    init: async () => {
      return
    },
    getStaticParamsList: async () => {
      if (delay) await new Promise((resolve) => setTimeout(resolve, delay))
      if (shouldError) throw new Error('Failed to load static params')
      return staticParams
    },
    getDynamicMetricsNames: async () => {
      return Object.keys(dynamicMetrics)
    },
    getDynamicMetricData: async (metricName: string) => {
      return [dynamicMetrics[metricName]]
    },
    getEvalsList: async () => {
      if (delay) await new Promise((resolve) => setTimeout(resolve, delay))
      if (shouldError) throw new Error('Failed to load evals')
      return evalsList
    },
    getSpansList: async (params: SpansParams) => {
      return []
    },
    buildSpanTree: async () => {
      return []
    },
    getTraceId: async (params: SpansParams) => {
      return `trace-${params.evalId}`
    },
  }
}

const mockModelsInfo: ModelsInfo = {
  'model-1': {
    name: 'GPT-4 Turbo',
    color: '#3b82f6',
  },
}

const multipleModelsInfo: ModelsInfo = {
  'model-1': {
    name: 'GPT-4 Turbo',
    color: '#3b82f6',
  },
  'model-2': {
    name: 'Claude 3 Opus',
    color: '#3b82f6',
  },
  'model-3': {
    name: 'Gemini Pro',
    color: '#3b82f6',
  },
}

const mockEvalsList: Record<string, EvalsInfo[]> = {
  'dataset-1': [
    {
      id: 'eval-1',
      dataset_id: 'dataset-1',
      inputs: {
        prompt: 'What is the capital of France?',
        context: 'Geography question',
        temperature: 0.7,
      },
      outputs: {
        response: 'The capital of France is Paris.',
        tokens_used: 45,
      },
      refs: {
        expected: 'Paris',
        category: 'geography',
      },
      scores: {
        metric_0: 1.0,
        coherence: 0.95,
        relevance: 0.98,
      },
      metadata: {
        timestamp: Date.now() - 3600000,
        model_version: 1,
        duration_ms: 1250,
      },
      modelId: 'model-1',
    },
    {
      id: 'eval-2',
      dataset_id: 'dataset-1',
      inputs: {
        prompt: 'Explain quantum computing in simple terms',
        context: 'Technical question',
        temperature: 0.5,
      },
      outputs: {
        response:
          'Quantum computing uses quantum mechanics principles like superposition and entanglement to process information in ways that classical computers cannot. Instead of traditional bits (0 or 1), quantum computers use qubits which can exist in multiple states simultaneously.',
        tokens_used: 156,
      },
      refs: {
        expected: 'A clear, accessible explanation of quantum computing',
        category: 'science',
      },
      scores: {
        metric_0: 0.88,
        coherence: 0.92,
        completeness: 0.85,
        simplicity: 0.9,
      },
      metadata: {
        timestamp: Date.now() - 7200000,
        model_version: 1,
        duration_ms: 2100,
      },
      modelId: 'model-1',
    },
    {
      id: 'eval-3',
      dataset_id: 'dataset-1',
      inputs: {
        prompt: 'Write a haiku about spring',
        context: 'Creative writing',
        temperature: 0.9,
      },
      outputs: {
        response: 'Cherry blossoms fall\nGentle breeze carries petals\nSpring awakens life',
        tokens_used: 28,
      },
      refs: {
        expected: 'A haiku with spring theme, 5-7-5 syllable structure',
        category: 'creative',
      },
      scores: {
        metric_0: 0.95,
        creativity: 0.97,
        structure: 1.0,
        imagery: 0.94,
      },
      metadata: {
        timestamp: Date.now() - 10800000,
        model_version: 1,
        duration_ms: 980,
      },
      modelId: 'model-1',
    },
  ] as EvalsInfo[],
}

const meta: Meta<typeof ExperimentSnapshot> = {
  title: 'Modules/ExperimentSnapshot',
  component: ExperimentSnapshot,
  tags: ['autodocs'],
  parameters: {
    layout: 'fullscreen',
    docs: {
      description: {
        component:
          'A component for displaying a snapshot of a model experiment. Shows static parameters, dynamic metrics, and evals results using PrimeVue components.',
      },
    },
  },
  argTypes: {
    modelsIds: {
      control: 'object',
      description: 'Array of model IDs to display',
    },
    modelsInfo: {
      control: 'object',
      description: 'Model information',
    },
  },
  decorators: [
    (story) => ({
      components: { story, Toast, StorybookPageWrapper },
      template: `
        <StorybookPageWrapper>
          <Toast />
          <story />
        </StorybookPageWrapper>
      `,
    }),
  ],
}

export default meta
type Story = StoryObj<typeof meta>

export const SingleModel: Story = {
  args: {
    provider: createMockProvider(),
    modelsIds: ['model-1'],
    modelsInfo: mockModelsInfo,
  },
  parameters: {
    docs: {
      description: {
        story:
          'Basic view with one model. Displays static parameters (eval_dataset, eval_version, evaluation_metrics, model_type) and dynamic metrics (metric_0, metric_1, metric_4 charts) using PrimeVue Card and Chart components.',
      },
    },
  },
}

export const MultipleModels: Story = {
  args: {
    provider: createMockProvider({
      staticParams: [
        {
          modelId: 'model-1',
          eval_dataset: 'test-dataset-v1',
          eval_version: '1.0.0',
          evaluation_metrics: ['metric_0', 'metric_1', 'metric_6'],
          model_type: 'gpt-4',
        },
        {
          modelId: 'model-2',
          eval_dataset: 'test-dataset-v1',
          eval_version: '1.0.0',
          evaluation_metrics: ['metric_0', 'metric_1', 'metric_6', 'recall'],
          model_type: 'claude-3-opus',
        },
        {
          modelId: 'model-3',
          eval_dataset: 'test-dataset-v1',
          eval_version: '1.0.0',
          evaluation_metrics: ['metric_0', 'metric_1'],
          model_type: 'gemini-pro',
        },
      ],
      dynamicMetrics: {
        metric_0: {
          x: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
          y: [0.85, 0.87, 0.89, 0.91, 0.93, 0.94, 0.95, 0.95, 0.96, 0.96],
          modelId: 'model-1',
          aggregated: false,
        },
        metric_1: {
          x: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
          y: [0.82, 0.84, 0.86, 0.88, 0.9, 0.91, 0.92, 0.92, 0.93, 0.93],
          modelId: 'model-2',
          aggregated: false,
        },
        metric_4: {
          x: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
          y: [180, 175, 170, 165, 160, 158, 155, 153, 150, 148],
          modelId: 'model-3',
          aggregated: false,
        },
      },
    }),
    modelsIds: ['model-1', 'model-2', 'model-3'],
    modelsInfo: multipleModelsInfo,
  },
  parameters: {
    docs: {
      description: {
        story:
          'Comparison of different models. Uses the StaticParametersMultiple component to display the parameters in a comparison table..',
      },
    },
  },
}

export const ManyMetrics: Story = {
  args: {
    provider: createMockProvider({
      staticParams: [
        {
          modelId: 'model-1',
          eval_dataset: 'comprehensive-dataset-v2',
          eval_version: '2.1.0',
          evaluation_metrics: [
            'metric_0',
            'metric_1',
            'metric_6',
            'recall',
            'auc_roc',
            'perplexity',
          ],
          model_type: 'gpt-4-turbo-preview',
        },
      ],
      dynamicMetrics: {
        metric_0: {
          x: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
          y: [
            0.75, 0.78, 0.81, 0.83, 0.85, 0.87, 0.88, 0.89, 0.9, 0.91, 0.92, 0.92, 0.93, 0.93, 0.94,
          ],
          modelId: 'model-1',
          aggregated: false,
        },
        metric_1: {
          x: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
          y: [
            0.72, 0.75, 0.78, 0.8, 0.82, 0.84, 0.85, 0.86, 0.87, 0.88, 0.89, 0.89, 0.9, 0.9, 0.91,
          ],
          modelId: 'model-1',
          aggregated: false,
        },

        metric_3: {
          x: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
          y: [
            0.7, 0.73, 0.76, 0.79, 0.81, 0.83, 0.85, 0.86, 0.87, 0.88, 0.89, 0.9, 0.9, 0.91, 0.91,
          ],
          modelId: 'model-1',
          aggregated: false,
        },
        metric_6: {
          x: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
          y: [
            0.7, 0.73, 0.76, 0.79, 0.81, 0.83, 0.85, 0.86, 0.87, 0.88, 0.89, 0.9, 0.9, 0.91, 0.91,
          ],
          modelId: 'model-1',
          aggregated: false,
        },
        metric_4: {
          x: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
          y: [150, 145, 140, 135, 130, 128, 125, 123, 120, 118, 117, 116, 115, 115, 114],
          modelId: 'model-1',
          aggregated: false,
        },
        metric_5: {
          x: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
          y: [
            0.05, 0.048, 0.046, 0.045, 0.044, 0.043, 0.042, 0.041, 0.04, 0.039, 0.038, 0.038, 0.037,
            0.037, 0.036,
          ],
          modelId: 'model-1',
          aggregated: false,
        },
      },
    }),
    modelsIds: ['model-1'],
    modelsInfo: mockModelsInfo,
  },
  parameters: {
    docs: {
      description: {
        story: 'Display with a large number of metrics ',
      },
    },
  },
}

export const NoStaticParams: Story = {
  args: {
    provider: createMockProvider({
      staticParams: [],
    }),
    modelsIds: ['model-1'],
    modelsInfo: mockModelsInfo,
  },
  parameters: {
    docs: {
      description: {
        story: 'Display without static parameters, only with dynamic metrics and evals.',
      },
    },
  },
}

export const NoDynamicMetrics: Story = {
  args: {
    provider: createMockProvider({
      dynamicMetrics: {},
    }),
    modelsIds: ['model-1'],
    modelsInfo: mockModelsInfo,
  },
  parameters: {
    docs: {
      description: {
        story: 'Display without dynamic metrics, only with static parameters and evals.',
      },
    },
  },
}

export const DifferentDatasetVersions: Story = {
  args: {
    provider: createMockProvider({
      staticParams: [
        {
          modelId: 'model-1',
          eval_dataset: 'dataset-v1',
          eval_version: '1.0.0',
          evaluation_metrics: ['metric_0', 'metric_1'],
          model_type: 'gpt-4',
        },
        {
          modelId: 'model-2',
          eval_dataset: 'dataset-v2',
          eval_version: '2.0.0',
          evaluation_metrics: ['metric_0', 'metric_1', 'metric_6'],
          model_type: 'claude-3',
        },
      ],
    }),
    modelsIds: ['model-1', 'model-2'],
    modelsInfo: {
      'model-1': { name: 'GPT-4 (v1)', color: '#3b82f6' },
      'model-2': { name: 'Claude-3 (v2)', color: '#3b82f6' },
    },
  },
  parameters: {
    docs: {
      description: {
        story:
          'Compare models with different dataset versions and different evaluation metrics. Shows how the component handles differences in parameters.',
      },
    },
  },
}
