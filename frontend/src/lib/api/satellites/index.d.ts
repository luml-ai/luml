import type { AxiosInstance } from 'axios';
import type { CreateSatellitePayload } from './interfaces';
export declare class SatellitesApi {
    private api;
    constructor(api: AxiosInstance);
    create(organizationId: string, orbitId: string, payload: CreateSatellitePayload): Promise<any>;
    update(organizationId: string, orbitId: string, satelliteId: string, payload: CreateSatellitePayload): Promise<any>;
    getList(organizationId: string, orbitId: string): Promise<any>;
    getItem(organizationId: string, orbitId: string, satelliteId: string): Promise<any>;
    delete(organizationId: string, orbitId: string, satelliteId: string): Promise<any>;
    regenerateApiKye(organizationId: string, orbitId: string, satelliteId: string): Promise<any>;
}
