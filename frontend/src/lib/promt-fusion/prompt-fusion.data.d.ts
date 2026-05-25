import { type BaseProviderInfo, type ProviderModel, type ProviderWithModels } from './prompt-fusion.interfaces';
export declare const getProviders: () => BaseProviderInfo[];
export declare const openAiModels: ProviderModel[];
export declare const ollamaModels: ProviderModel[];
export declare const getAllModels: () => ProviderWithModels[];
export declare const allModels: ProviderWithModels[];
