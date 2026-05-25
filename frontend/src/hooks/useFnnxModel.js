import { Model } from '@fnnx-ai/web';
import { computed, ref } from 'vue';
import { FnnxService } from '@/lib/fnnx/FnnxService';
import { DataProcessingWorker } from '@/lib/data-processing/DataProcessingWorker';
export const useFnnxModel = () => {
    const buffer = ref(null);
    const model = ref(null);
    const currentTag = ref(null);
    const modelId = ref(null);
    const getModel = computed(() => model.value);
    async function createModelFromFile(file) {
        const availableExtensions = ['.luml', '.dfs'];
        const isCorrectExtension = availableExtensions.some((extension) => file.name.endsWith(extension));
        if (!isCorrectExtension)
            throw new Error('Incorrect file format');
        buffer.value = await file.arrayBuffer();
        model.value = await Model.fromBuffer(buffer.value);
        currentTag.value = FnnxService.getTypeTag(model.value.getManifest());
        const isPythonModel = model.value.getManifest().variant === 'pyfunc';
        if (isPythonModel) {
            await initPythonModel();
        }
        else {
            await model.value.warmup();
        }
    }
    function removeModel() {
        buffer.value = null;
        model.value = null;
        currentTag.value = null;
        deinit();
    }
    async function initPythonModel() {
        if (!buffer.value)
            throw new Error('First create a model');
        const result = await DataProcessingWorker.initPythonModel(buffer.value);
        if (result.status === 'success') {
            modelId.value = result.model_id;
        }
        else {
            throw new Error(result.error_message);
        }
    }
    async function deinit() {
        if (!modelId.value)
            return;
        return DataProcessingWorker.deinitPythonModel(modelId.value);
    }
    return { currentTag, getModel, modelId, createModelFromFile, removeModel, deinit };
};
