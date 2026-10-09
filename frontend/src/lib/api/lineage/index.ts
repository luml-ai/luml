import type { AxiosInstance } from 'axios'
import type {
  LineageBatchIn,
  LineageBatchResult,
  LineageCreateIn,
  LineageEdge,
  LineageGraph,
} from './interfaces'

export class LineageApi {
  private api: AxiosInstance

  constructor(api: AxiosInstance) {
    this.api = api
  }

  /**
   * Loads the graph around an artifact. Without `depth` the platform returns
   * the whole connected component; its only limit is the 200-artifact cap.
   */
  async getGraph(
    organizationId: string,
    orbitId: string,
    artifactId: string,
    depth?: number,
  ): Promise<LineageGraph> {
    const { data } = await this.api.get<LineageGraph>(
      `/v1/organizations/${organizationId}/orbits/${orbitId}/artifacts/${artifactId}/lineage`,
      { params: depth === undefined ? {} : { depth } },
    )
    return data
  }

  async createLinks(
    organizationId: string,
    orbitId: string,
    sourceArtifactId: string,
    targetArtifactIds: string[],
  ): Promise<LineageEdge[]> {
    const payload: LineageCreateIn = { target_artifact_ids: targetArtifactIds }
    const { data } = await this.api.post<LineageEdge[]>(
      `/v1/organizations/${organizationId}/orbits/${orbitId}/artifacts/${sourceArtifactId}/lineage`,
      payload,
    )
    return data
  }

  async deleteLink(
    organizationId: string,
    orbitId: string,
    artifactId: string,
    edgeId: string,
  ): Promise<LineageEdge> {
    const { data } = await this.api.delete<LineageEdge>(
      `/v1/organizations/${organizationId}/orbits/${orbitId}/artifacts/${artifactId}/lineage/${edgeId}`,
    )
    return data
  }

  async applyChanges(
    organizationId: string,
    orbitId: string,
    changes: LineageBatchIn,
  ): Promise<LineageBatchResult> {
    const { data } = await this.api.post<LineageBatchResult>(
      `/v1/organizations/${organizationId}/orbits/${orbitId}/lineage/batch`,
      changes,
    )
    return data
  }
}
