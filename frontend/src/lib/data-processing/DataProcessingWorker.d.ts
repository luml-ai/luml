import { WEBWORKER_ROUTES_ENUM, WebworkerMessage, type PredictRequestData, type PromptOptimizationData, type TaskPayload } from './interfaces';
declare class DataProcessingWorkerClass {
    private callbacks;
    private callbackId;
    constructor();
    sendMessage(message: WebworkerMessage, route?: WEBWORKER_ROUTES_ENUM, data?: any): Promise<any>;
    initPyodide(): Promise<boolean>;
    saveModel(modelBlob: Blob, fileName: string): void;
    checkPyodideReady(): Promise<void>;
    startTraining(data: TaskPayload | PromptOptimizationData, route: WEBWORKER_ROUTES_ENUM.TABULAR_TRAIN | WEBWORKER_ROUTES_ENUM.PROMPT_OPTIMIZATION_TRAIN): Promise<any>;
    startPredict(data: PredictRequestData, route: WEBWORKER_ROUTES_ENUM.TABULAR_PREDICT | WEBWORKER_ROUTES_ENUM.PROMPT_OPTIMIZATION_PREDICT): Promise<any>;
    deallocateModels(models: string[], route: WEBWORKER_ROUTES_ENUM.TABULAR_DEALLOCATE | WEBWORKER_ROUTES_ENUM.STORE_DEALLOCATE): Promise<any[]>;
    interrupt(): Promise<void>;
    initPythonModel(model: ArrayBuffer): Promise<{
        model_id: string;
        status: 'success';
    } | {
        status: 'error';
        error_message: string;
    }>;
    computePythonModel(payload: {
        model_id: string;
        inputs: object;
        dynamic_attributes: object;
    }): Promise<{
        status: 'success';
        predictions: Record<string, Record<string, string>>;
    } | {
        status: 'error';
        error_type: string;
        error_message: string;
    }>;
    deinitPythonModel(modelId: string): Promise<any>;
}
export declare const DataProcessingWorker: DataProcessingWorkerClass;
export {};
