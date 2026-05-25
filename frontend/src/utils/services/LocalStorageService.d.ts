import type { LocalStorageProviderSettings } from './LocalStorageService.interfaces';
type StorageValueMap = {
    providersSettings: LocalStorageProviderSettings;
    currentOrganizationId: string;
};
type StorageKey = keyof StorageValueMap;
declare class LocalStorageServiceClass {
    get<K extends StorageKey>(key: K): StorageValueMap[K] | null;
    set<K extends StorageKey>(key: K, value: StorageValueMap[K]): void;
    remove<K extends StorageKey>(key: K): void;
    clear(): void;
}
export declare const LocalStorageService: LocalStorageServiceClass;
export {};
