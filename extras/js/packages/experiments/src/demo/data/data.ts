import type {
  EvalsInfo,
  ExperimentSnapshotDynamicMetrics,
  ExperimentSnapshotProvider,
  ExperimentSnapshotStaticParams,
  SpansParams,
} from '@/interfaces/interfaces'

export const createMockProvider = (
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
      const data = dynamicMetrics[metricName]
      return data ? [data] : []
    },
    getEvalsList: async () => {
      if (delay) await new Promise((resolve) => setTimeout(resolve, delay))
      if (shouldError) throw new Error('Failed to load evals')
      return evalsList
    },
    getTraceSpans: async (modelId: string, traceId: string) => {
      return [
        {
          modelId,
          trace_id: traceId,
          span_id: 'span-1',
          parent_span_id: null,
          name: 'span-1',
          kind: 0,
          start_time_unix_nano: 1716796800000000000,
          end_time_unix_nano: 1716796800000000000,
          status_code: 200,
          status_message: 'OK',
          attributes: '{}',
          events: '{}',
          links: '{}',
          dfs_span_type: 0,
        },
        {
          modelId,
          trace_id: traceId,
          span_id: 'span-2',
          parent_span_id: 'span-1',
          name: 'trace-2',
          kind: 0,
          start_time_unix_nano: 1716796800000000000,
          end_time_unix_nano: 1716796800000000000,
          status_code: 200,
          status_message: 'OK',
          attributes: '{}',
          events: '{}',
          links: '{}',
          dfs_span_type: 0,
        },
      ]
    },
    buildSpanTree: async () => {
      return [
        {
          trace_id: 'trace-1',
          span_id: 'span-1',
          parent_span_id: null,
          name: 'span-1',
          kind: 0,
          start_time_unix_nano: 1716796800000000000,
          end_time_unix_nano: 1716796800000000000,
          status_code: 200,
          status_message: 'OK',
          attributes: '{}',
          events: '{}',
          links: '{}',
          dfs_span_type: 0,
          children: [],
        },
        {
          trace_id: 'trace-1',
          span_id: 'span-2',
          parent_span_id: 'span-1',
          name: 'span-2',
          kind: 0,
          start_time_unix_nano: 1716796800000000000,
          end_time_unix_nano: 1716796800000000000,
          status_code: 200,
          status_message: 'OK',
          attributes: '{}',
          events: '{}',
          links: '{}',
          dfs_span_type: 0,
          children: [],
        },
        {
          trace_id: 'trace-1',
          span_id: 'span-3',
          parent_span_id: 'span-2',
          name: 'span-3',
          kind: 0,
          start_time_unix_nano: 1716796800000000000,
          end_time_unix_nano: 1716796800000000000,
          status_code: 200,
          status_message: 'OK',
          attributes: '{}',
          events: '{}',
          links: '{}',
          dfs_span_type: 0,
          children: [],
        },
      ]
    },
    getTraceId: async (params: SpansParams) => {
      return `trace-${params.evalId}`
    },
    getUniqueTraceIds: async (modelId: string) => {
      if (!modelId) return []
      return ['trace-1', 'trace-2']
    },
  }
}
