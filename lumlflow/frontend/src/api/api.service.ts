import type { DetailedGroup, Group, UpdateGroupPayload } from '@/store/groups/groups.interface'
import type {
  GetExperimentsParams,
  GetExperimentTracesParams,
  GetGroupsParams,
  PaginatedResponse,
  UpdateModelPayload,
} from './api.interface'
import { api } from './client'
import type {
  Experiment,
  ExperimentMetricHistory,
  Model,
  Trace,
  UpdateExperimentPayload,
} from '@/store/experiments/experiments.interface'

export const apiService = {
  getGroups: async (params: GetGroupsParams) => {
    const { data } = await api.get<PaginatedResponse<Group>>('/experiment-groups', { params })
    return data
  },

  getGroup: async (groupId: string) => {
    const { data } = await api.get<Group>(`/experiment-groups/${groupId}/details`)
    return data
  },

  updateGroup: async (groupId: string, payload: UpdateGroupPayload) => {
    const { data } = await api.patch<Group>(`/experiment-groups/${groupId}`, payload)
    return data
  },

  deleteGroup: async (groupId: string) => {
    const { data } = await api.delete<Group>(`/experiment-groups/${groupId}`)
    return data
  },

  getGroupById: async (groupId: string) => {
    const { data } = await api.get<DetailedGroup>(`/experiment-groups/${groupId}/details`)
    return data
  },

  getExperiments: async (params: GetExperimentsParams) => {
    const { group_id, ...rest } = params
    const { data } = await api.get<PaginatedResponse<Experiment>>(
      `/experiment-groups/${group_id}/experiments`,
      { params: rest },
    )
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

  getExperimentMetricHistory: async (experimentId: string, metricKey: string) => {
    const { data } = await api.get<ExperimentMetricHistory>(
      `/experiments/${experimentId}/metrics/${metricKey}`,
    )
    return data
  },

  getExperimentModels: async (experimentId: string) => {
    const { data } = await api.get<Model[]>(`/experiments/${experimentId}/models`)
    return data
  },

  getExperimentTraces: async (experimentId: string, params: GetExperimentTracesParams) => {
    const { data } = await api.get<PaginatedResponse<Trace>>(
      `/experiments/${experimentId}/traces`,
      { params },
    )
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

  getLumlOrganizations: async () => {
    const { data } = await api.get('/luml/organizations')
    return data
  },

  getLumlOrbits: async (organizationId: string) => {
    const { data } = await api.get('/luml/orbits', {
      params: { organization_id: organizationId },
    })
    return data
  },

  getLumlCollections: async (
    organizationId: string,
    orbitId: string,
    search?: string,
  ) => {
    const { data } = await api.get('/luml/collections', {
      params: { organization_id: organizationId, orbit_id: orbitId, search },
    })
    return data
  },

  uploadLumlArtifact: async (payload: {
    upload_type: 'auto' | 'model' | 'experiment'
    experiment_id: string
    organization_id: string
    orbit_id: string
    collection_id: string
    name?: string
    description?: string
    tags?: string[]
    embed_experiment?: boolean
  }) => {
    const { data } = await api.post<{ job_id: string }>('/luml/artifact', payload)
    return data
  },
}
