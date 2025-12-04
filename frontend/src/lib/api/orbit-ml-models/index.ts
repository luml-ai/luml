import type { AxiosInstance } from 'axios'
import type {
  CreateModelResponse,
  MlModel,
  MlModelCreator,
  UpdateMlModelPayload,
} from './interfaces'

export class MlModelsApi {
  private api: AxiosInstance

  constructor(api: AxiosInstance) {
    this.api = api
  }

  async createModel(
    organizationId: string,
    orbitId: string,
    collectionId: string,
    data: MlModelCreator,
  ) {
    const { data: responseData } = await this.api.post<CreateModelResponse>(
      `/organizations/${organizationId}/orbits/${orbitId}/collections/${collectionId}/model_artifacts`,
      data,
    )
    return responseData
  }

  async getModelsList(organizationId: string, orbitId: string, collectionId: string) {
    const { data: responseData } = await this.api.get<MlModel[]>(
      `/organizations/${organizationId}/orbits/${orbitId}/collections/${collectionId}/model_artifacts`,
    )
    return responseData
  }

  async updateModel(
    organizationId: string,
    orbitId: string,
    collectionId: string,
    modelId: string,
    data: UpdateMlModelPayload,
  ) {
    const { data: responseData } = await this.api.patch<MlModel>(
      `/organizations/${organizationId}/orbits/${orbitId}/collections/${collectionId}/model_artifacts/${modelId}`,
      data,
    )
    return responseData
  }

  async getModelDownloadUrl(
    organizationId: string,
    orbitId: string,
    collectionId: string,
    modelId: string,
  ) {
    const { data: responseData } = await this.api.get<{ url: string }>(
      `/organizations/${organizationId}/orbits/${orbitId}/collections/${collectionId}/model_artifacts/${modelId}/download-url`,
    )
    return responseData
  }

  async getModelDeleteUrl(
    organizationId: string,
    orbitId: string,
    collectionId: string,
    modelId: string,
  ) {
    const { data: responseData } = await this.api.get<{ url: string }>(
      `/organizations/${organizationId}/orbits/${orbitId}/collections/${collectionId}/model_artifacts/${modelId}/delete-url`,
    )
    return responseData
  }

  async confirmModelDelete(
    organizationId: string,
    orbitId: string,
    collectionId: string,
    modelId: string,
  ) {
    const { data: responseData } = await this.api.delete(
      `/organizations/${organizationId}/orbits/${orbitId}/collections/${collectionId}/model_artifacts/${modelId}`,
    )
    return responseData
  }

  async forceDelete(
    organizationId: string,
    orbitId: string,
    collectionId: string,
    modelId: string,
  ) {
    return this.api.delete(
      `/organizations/${organizationId}/orbits/${orbitId}/collections/${collectionId}/model_artifacts/${modelId}/force`,
    )
  }
}
