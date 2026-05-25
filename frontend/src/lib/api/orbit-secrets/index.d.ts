import type { AxiosInstance } from 'axios';
import type { CreateSecretPayload, UpdateSecretPayload } from './interfaces';
export declare class OrbitSecretsApi {
    private api;
    constructor(api: AxiosInstance);
    getSecrets(organizationId: string, orbitId: string): Promise<any>;
    getSecretById(organizationId: string, orbitId: string, secretId: string): Promise<any>;
    createSecret(organizationId: string, orbitId: string, payload: CreateSecretPayload): Promise<any>;
    updateSecret(organizationId: string, orbitId: string, payload: UpdateSecretPayload): Promise<any>;
    deleteSecret(organizationId: string, orbitId: string, secretId: string): Promise<any>;
}
