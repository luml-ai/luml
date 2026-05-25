import type { AxiosInstance } from 'axios';
import type { CreateDeploymentPayload, UpdateDeploymentPayload } from './interfaces';
export declare class DeploymentsApi {
    private api;
    constructor(api: AxiosInstance);
    create(organizationId: string, orbitId: string, payload: CreateDeploymentPayload): Promise<any>;
    getList(organizationId: string, orbitId: string): Promise<any>;
    getDeployment(organizationId: string, orbitId: string, deploymentId: string): Promise<any>;
    deleteDeployment(organizationId: string, orbitId: string, deploymentId: string): Promise<any>;
    update(organizationId: string, orbitId: string, deploymentId: string, payload: UpdateDeploymentPayload): Promise<any>;
    forceDeleteDeployment(organizationId: string, orbitId: string, deploymentId: string): Promise<any>;
}
