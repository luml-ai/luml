import type { DetailedGroup, Group, UpdateGroupPayload } from '@/store/groups/groups.interface'
import type {
  GetExperimentsParams,
  GetExperimentTracesParams,
  GetGroupsParams,
  PaginatedResponse,
  UpdateModelPayload,
  CheckAuthResponse,
  GetExperimentEvalsParams,
  AverageScore,
  AddAnnotationPayload,
  UpdateAnnotationPayload,
  Annotation,
  AnnotationSummary,
  GetLumlCollectionsParams,
  UploadArtifactResponse,
  ValidateExperimentSearchResponse,
} from './api.interface'
import { api } from './client'
import type {
  Eval,
  EvalScores,
  Experiment,
  ExperimentMetricHistory,
  Model,
  Trace,
  TraceDetails,
  UpdateExperimentPayload,
} from '@/store/experiments/experiments.interface'
import qs from 'qs'
import type {
  CollectionInfo,
  OrbitInfo,
  OrganizationInfo,
  UploadArtifactPayload,
} from '@/components/upload/upload.interface'

export const apiService = {
  getGroups: async (params: GetGroupsParams) => {
    const { data } = await api.get<PaginatedResponse<Group>>('/groups', { params })
    return data
  },

  getGroup: async (groupId: string) => {
    const { data } = await api.get<Group>(`/groups/${groupId}/details`)
    return data
  },

  updateGroup: async (groupId: string, payload: UpdateGroupPayload) => {
    const { data } = await api.patch<Group>(`/groups/${groupId}`, payload)
    return data
  },

  deleteGroup: async (groupId: string) => {
    const { data } = await api.delete<Group>(`/groups/${groupId}`)
    return data
  },

  getGroupById: async (groupId: string) => {
    const { data } = await api.get<DetailedGroup>(`/groups/${groupId}/details`)
    return data
  },

  getGroupsDynamicMetrics: async (groupIds: string[]) => {
    const { data } = await api.get<string[]>(`/groups/experiments/dynamic-metrics`, {
      paramsSerializer: (params) => qs.stringify(params, { arrayFormat: 'repeat' }),
      params: { group_ids: groupIds },
    })
    return data
  },

  getGroupsStaticParams: async (group_ids: string[]) => {
    const { data } = await api.get<string[]>(`/groups/experiments/static-params`, {
      params: { group_ids },
      paramsSerializer: (params) => qs.stringify(params, { arrayFormat: 'repeat' }),
    })
    return data
  },

  getExperiments: async (params: GetExperimentsParams) => {
    const { data } = await api.get<PaginatedResponse<Experiment>>(`/groups/experiments`, {
      params,
      paramsSerializer: (params) => qs.stringify(params, { arrayFormat: 'repeat' }),
    })
    return data
  },

  getExperiment: async (experimentId: string) => {
    const { data } = await api.get<Experiment>(`/experiments/${experimentId}`)
    return data
  },

  updateExperiment: async (experimentId: string, payload: UpdateExperimentPayload) => {
    const { data } = await api.patch<Experiment>(`/experiments/${experimentId}`, payload)
    return data
  },

  deleteExperiment: async (experimentId: string) => {
    const { data } = await api.delete<Experiment>(`/experiments/${experimentId}`)
    return data
  },

  getExperimentMetricHistory: async (
    experimentId: string,
    metricKey: string,
    maxPoints: number = 1000,
    signal?: AbortSignal,
  ) => {
    const { data } = await api.get<ExperimentMetricHistory>(
      `/experiments/${experimentId}/metrics/${encodeURIComponent(metricKey)}`,
      { params: { max_points: maxPoints }, signal },
    )
    return data
  },

  getExperimentModels: async (experimentId: string) => {
    const { data } = await api.get<Model[]>(`/experiments/${experimentId}/models`)
    return data
  },

  getExperimentTraces: async (params: GetExperimentTracesParams) => {
    const { experiment_id, ...rest } = params
    const { data } = await api.get<PaginatedResponse<Trace>>(
      `/experiments/${experiment_id}/traces`,
      { params: rest },
    )
    return data
  },

  getAllExperimentTraces: async (params: GetExperimentTracesParams) => {
    const { experiment_id, ...rest } = params
    const { data } = await api.get<Trace[]>(`/experiments/${experiment_id}/traces/all`, {
      params: rest,
    })
    return data
  },

  getTraceDetails: async (experimentId: string, traceId: string) => {
    const { data } = await api.get<TraceDetails>(`/experiments/${experimentId}/traces/${traceId}`)
    return data
  },

  updateModel: async (modelId: string, payload: UpdateModelPayload) => {
    const { data } = await api.patch<Model>(`/models/${modelId}`, payload)
    return data
  },

  deleteModel: async (modelId: string) => {
    const { data } = await api.delete<void>(`/models/${modelId}`)
    return data
  },

  checkAuth: async () => {
    const { data } = await api.get<CheckAuthResponse>('/auth/status')
    return data
  },

  setApiKey: async (apiKey: string) => {
    const { data } = await api.post<void>('/auth/api-key', { api_key: apiKey })
    return data
  },

  getExperimentEvals: async (params: GetExperimentEvalsParams) => {
    const { experiment_id, ...rest } = params
    const { data } = await api.get<PaginatedResponse<Eval>>(`/experiments/${experiment_id}/evals`, {
      params: rest,
    })
    return data
  },

  getAllExperimentEvals: async (params: Omit<GetExperimentEvalsParams, 'limit'>) => {
    const { experiment_id, ...rest } = params
    const { data } = await api.get<Eval[]>(`/experiments/${experiment_id}/evals/all`, {
      params: rest,
    })
    return data
  },

  getEvalById: async (experimentId: string, evalId: string) => {
    const { data } = await api.get<Eval>(`/experiments/${experimentId}/evals/${evalId}`)
    return data
  },

  getExperimentEvalColumns: async (experimentId: string, datasetId: string) => {
    const { data } = await api.get<EvalScores>(`/experiments/${experimentId}/evals/columns`, {
      params: { dataset_id: datasetId },
    })
    return data
  },

  getExperimentDatasetAverageScores: async (
    experimentId: string,
    datasetId: string,
  ): Promise<AverageScore[]> => {
    const { data } = await api.get<{ [name: string]: number }>(
      `/experiments/${experimentId}/evals/average-scores`,
      {
        params: { dataset_id: datasetId },
      },
    )
    return Object.entries(data).map(([name, value]) => ({ name, value }))
  },

  getExperimentUniqueDatasetsIds: async (experimentId: string) => {
    const { data } = await api.get<string[]>(`/experiments/${experimentId}/evals/dataset-ids`)
    return data
  },

  // --- Annotations ---

  createEvalAnnotation: async (
    experimentId: string,
    datasetId: string,
    evalId: string,
    payload: AddAnnotationPayload,
  ) => {
    const { data } = await api.post<Annotation>(
      `/experiments/${experimentId}/evals/${datasetId}/${evalId}/annotations`,
      payload,
    )
    return data
  },

  updateEvalAnnotation: async (
    experimentId: string,
    annotationId: string,
    payload: UpdateAnnotationPayload,
  ) => {
    const { data } = await api.patch<Annotation>(
      `/experiments/${experimentId}/eval-annotations/${annotationId}`,
      payload,
    )
    return data
  },

  getEvalAnnotations: async (experimentId: string, datasetId: string, evalId: string) => {
    const { data } = await api.get<Annotation[]>(
      `/experiments/${experimentId}/evals/${datasetId}/${evalId}/annotations`,
    )
    return data
  },

  deleteEvalAnnotation: async (experimentId: string, annotationId: string) => {
    const { data } = await api.delete<void>(
      `/experiments/${experimentId}/eval-annotations/${annotationId}`,
    )
    return data
  },

  getEvalAnnotationSummary: async (experimentId: string, datasetId: string) => {
    const { data } = await api.get<AnnotationSummary>(
      `/experiments/${experimentId}/evals/annotations/summary`,
      { params: { dataset_id: datasetId } },
    )
    return data
  },

  createSpanAnnotation: async (
    experimentId: string,
    traceId: string,
    spanId: string,
    payload: AddAnnotationPayload,
  ) => {
    const { data } = await api.post<Annotation>(
      `/experiments/${experimentId}/traces/${traceId}/spans/${spanId}/annotations`,
      payload,
    )
    return data
  },

  updateSpanAnnotation: async (
    experimentId: string,
    annotationId: string,
    payload: UpdateAnnotationPayload,
  ) => {
    const { data } = await api.patch<Annotation>(
      `/experiments/${experimentId}/span-annotations/${annotationId}`,
      payload,
    )
    return data
  },

  getSpanAnnotations: async (experimentId: string, traceId: string, spanId: string) => {
    const { data } = await api.get<Annotation[]>(
      `/experiments/${experimentId}/traces/${traceId}/spans/${spanId}/annotations`,
    )
    return data
  },

  deleteSpanAnnotation: async (experimentId: string, annotationId: string) => {
    const { data } = await api.delete<void>(
      `/experiments/${experimentId}/span-annotations/${annotationId}`,
    )
    return data
  },

  getTracesAnnotationSummary: async (experimentId: string) => {
    const { data } = await api.get<AnnotationSummary>(
      `/experiments/${experimentId}/traces/annotations/summary`,
    )
    return data
  },

  getLumlOrganizations: async () => {
    const { data } = await api.get<OrganizationInfo[]>(`/luml/organizations`)
    return data
  },

  getLumlOrbits: async (organizationId: string) => {
    const { data } = await api.get<OrbitInfo[]>(`/luml/orbits`, {
      params: { organization_id: organizationId },
    })
    return data
  },

  getLumlCollections: async (params: GetLumlCollectionsParams) => {
    const { data } = await api.get<PaginatedResponse<CollectionInfo>>(`/luml/collections`, {
      params,
    })
    return data
  },

  uploadArtifact: async (payload: UploadArtifactPayload) => {
    const { data } = await api.post<UploadArtifactResponse>(`/luml/artifact`, payload)
    return data
  },

  validateExperimentSearch: async (query: string) => {
    const { data } = await api.get<ValidateExperimentSearchResponse>(
      `/groups/experiments/validate-search`,
      {
        params: { query },
      },
    )
    return data
  },
}
