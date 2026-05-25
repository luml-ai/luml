export declare const useFnnxModel: () => {
    currentTag: any;
    getModel: any;
    modelId: any;
    createModelFromFile: (file: File) => Promise<void>;
    removeModel: () => void;
    deinit: () => Promise<any>;
};
