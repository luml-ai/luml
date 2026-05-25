import { ApiClass } from './api';
declare module 'axios' {
    interface AxiosRequestConfig {
        skipInterceptors?: boolean;
    }
}
export declare const api: ApiClass;
