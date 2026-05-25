const FILE_TYPES = {
    model: ['dfs', 'fnnx', 'pyfnx', 'luml'],
    experiment: ['luml'],
    dataset: ['tar'],
};
export const isCorrectFileName = (fileName) => {
    const regex = /^[^:\"*\`~#%;'^]+\.[^\s:\"*\`~#%;'^]+$/;
    return regex.test(fileName);
};
export const isModelFile = (fileName) => {
    return FILE_TYPES.model.some((type) => fileName.endsWith('.' + type));
};
export const isExperimentFile = (fileName) => {
    return FILE_TYPES.experiment.some((type) => fileName.endsWith('.' + type));
};
export const isDatasetFile = (fileName) => {
    return FILE_TYPES.dataset.some((type) => fileName.endsWith('.' + type));
};
