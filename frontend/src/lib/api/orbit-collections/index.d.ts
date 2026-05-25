import type { AxiosInstance } from 'axios';
import type { GetCollectionsListParams, OrbitCollectionCreator, ExtendedOrbitCollection } from './interfaces';
export declare class OrbitCollectionsApi {
    private api;
    constructor(api: AxiosInstance);
    getCollectionsList(organizationId: string, orbitId: string, params: GetCollectionsListParams): Promise<any>;
    createCollection(organizationId: string, orbitId: string, data: OrbitCollectionCreator): Promise<any>;
    updateCollection(organizationId: string, orbitId: string, collectionId: string, data: Omit<OrbitCollectionCreator, 'type'>): Promise<any>;
    deleteCollection(organizationId: string, orbitId: string, collectionId: string): Promise<any>;
    getCollection(organizationId: string, orbitId: string, collectionId: string): Promise<ExtendedOrbitCollection>;
}
