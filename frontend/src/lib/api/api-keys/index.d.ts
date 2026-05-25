import type { AxiosInstance } from 'axios';
export declare class ApiKeysApi {
    private api;
    constructor(api: AxiosInstance);
    createApiKey(): Promise<any>;
    deleteApiKey(): Promise<void>;
}
