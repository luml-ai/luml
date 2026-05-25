import { type PredictRequestData, type TaskPayload } from './../lib/data-processing/interfaces';
export declare const useModelTraining: (service: "tabular" | "prompt_optimization") => {
    isLoading: any;
    isTrainingSuccess: any;
    getTotalScore: any;
    getTestMetrics: any;
    getTrainingMetrics: any;
    getTop5Feature: any;
    isTrainMode: any;
    getPredictedData: any;
    trainingModelId: any;
    currentTask: any;
    modelBlob: any;
    startTraining: (data: TaskPayload) => Promise<void>;
    downloadModel: () => void;
    startPredict: (request: PredictRequestData) => Promise<any>;
};
