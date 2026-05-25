import type { AxiosInstance } from 'axios';
import type { GetArtifactsListParams, CreateArtifactPayload, UpdateArtifactPayload } from './interfaces';
export declare class ArtifactsApi {
    private api;
    constructor(api: AxiosInstance);
    create(organizationId: string, orbitId: string, collectionId: string, data: CreateArtifactPayload): Promise<any>;
    getList(organizationId: string, orbitId: string, collectionId: string, params: GetArtifactsListParams, signal: AbortSignal): Promise<any>;
    update(organizationId: string, orbitId: string, collectionId: string, artifactId: string, data: UpdateArtifactPayload): Promise<any>;
    getDownloadUrl(organizationId: string, orbitId: string, collectionId: string, artifactId: string): Promise<any>;
    getDeleteUrl(organizationId: string, orbitId: string, collectionId: string, artifactId: string): Promise<any>;
    confirmDelete(organizationId: string, orbitId: string, collectionId: string, artifactId: string): Promise<any>;
    forceDelete(organizationId: string, orbitId: string, collectionId: string, artifactId: string): Promise<any>;
    getById(organizationId: string, orbitId: string, collectionId: string, artifactId: string): Promise<any>;
}
