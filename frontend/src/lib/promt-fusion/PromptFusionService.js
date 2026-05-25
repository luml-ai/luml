import { Position } from '@vue-flow/core';
import { NodeTypeEnum, } from '@/components/express-tasks/prompt-fusion/interfaces';
import { Observable } from '@/utils/observable/Observable';
import { EvaluationModesEnum, ProviderStatus } from './prompt-fusion.interfaces';
import { allModels, getProviders } from './prompt-fusion.data';
import { parseProviderSettingsToObject } from '@/helpers/helpers';
import { DataProcessingWorker } from '../data-processing/DataProcessingWorker';
import { WEBWORKER_ROUTES_ENUM } from '../data-processing/interfaces';
const initialState = {
    availableModels: [],
    isSettingsOpened: false,
    openedProviderSettings: null,
    isOptimizationOpened: false,
    teacherModel: null,
    studentModel: null,
    evaluationMode: EvaluationModesEnum.none,
    evaluationCriteriaList: [],
    nodesData: null,
    payload: null,
    isTrainingActive: false,
    isPredictVisible: false,
    modelId: null,
    taskDescription: '',
    trainingData: null,
    predictionFields: null,
    modelBlob: null,
};
class PromptFusionServiceClass extends Observable {
    providers = getProviders();
    availableModels = initialState.availableModels;
    isSettingsOpened = initialState.isSettingsOpened;
    openedProviderSettings = initialState.openedProviderSettings;
    isOptimizationOpened = initialState.isOptimizationOpened;
    teacherModel = initialState.teacherModel;
    studentModel = initialState.studentModel;
    evaluationMode = initialState.evaluationMode;
    evaluationCriteriaList = initialState.evaluationCriteriaList;
    nodesData = initialState.nodesData;
    payload = initialState.payload;
    isTrainingActive = initialState.isTrainingActive;
    isPredictVisible = initialState.isPredictVisible;
    modelId = initialState.modelId;
    taskDescription = initialState.taskDescription;
    trainingData = initialState.trainingData;
    predictionFields = initialState.predictionFields;
    modelBlob = initialState.modelBlob;
    inputs = [];
    outputs = [];
    constructor() {
        super();
    }
    openSettings() {
        this.isSettingsOpened = true;
        this.emit('CHANGE_SETTINGS_STATUS', true);
    }
    closeSettings() {
        this.isSettingsOpened = false;
        this.emit('CHANGE_SETTINGS_STATUS', false);
    }
    openProviderSettings(provider) {
        this.openedProviderSettings = provider;
        this.emit('OPEN_PROVIDER_SETTINGS', this.openedProviderSettings);
    }
    updateProviderSettings(provider, settings) {
        const currentProvider = this.providers.find((prov) => prov.id === provider);
        if (!currentProvider)
            return;
        currentProvider.settings = settings;
        currentProvider.status = settings.filter((setting) => setting.required && !setting.value).length
            ? ProviderStatus.disconnected
            : ProviderStatus.connected;
        this.changeAvailableModels();
    }
    closeProviderSettings() {
        this.openedProviderSettings = null;
        this.emit('CLOSE_PROVIDER_SETTINGS');
    }
    changeOptimizationState(isOpen) {
        this.isOptimizationOpened = isOpen;
        this.emit('CHANGE_OPTIMIZATION_STATE', isOpen);
    }
    changeAvailableModels() {
        this.availableModels = allModels.filter((model) => this.getConnectedProviders().find((provider) => provider.id === model.providerId));
        this.emit('CHANGE_AVAILABLE_MODELS', this.availableModels);
    }
    updateTeacherModel(model) {
        this.teacherModel = model;
        this.emit('CHANGE_TEACHER_MODEL', model);
    }
    updateStudentModel(model) {
        this.studentModel = model;
        this.emit('CHANGE_STUDENT_MODEL', model);
    }
    checkIsOptimizationAvailable() {
        if (!this.teacherModel)
            throw new Error('Teacher model is required!');
        if (!this.studentModel)
            throw new Error('Student model is required!');
        if (!this.taskDescription)
            throw new Error('Task description is required!');
        if (this.haveDuplicatedFields())
            throw new Error('Optimization cannot proceed with identical field names in cards. Please review and rename duplicate fields.');
        if (!this.nodesData?.nodes?.length) {
            throw new Error('Pipeline has no nodes. Please build your pipeline first.');
        }
        if (!this.nodesData?.edges?.length) {
            throw new Error('Pipeline nodes are not connected. Please connect your nodes.');
        }
    }
    getProviderSettings(providerId) {
        return this.providers.find((provider) => provider.id === providerId)?.settings || [];
    }
    async runOptimization() {
        this.isTrainingActive = true;
        this.changeOptimizationState(false);
        this.emit('CHANGE_TRAINING_STATE', this.isTrainingActive);
        const result = await DataProcessingWorker.startTraining({ task_spec: this.payload }, WEBWORKER_ROUTES_ENUM.PROMPT_OPTIMIZATION_TRAIN);
        if (result.status === 'success' && result.model_id) {
            this.setModelId(result.model_id);
            this.savePredictionFields();
            this.endTraining();
            this.saveModel(result.model);
        }
        else {
            this.endTraining();
            throw new Error(result.error_message || 'Training failed');
        }
    }
    prepareData(object) {
        this.prepareNodesData(object);
        if (!this.nodesData)
            throw new Error('Failed to retrieve data');
        const optimizationSettings = {
            taskDescription: this.taskDescription,
            teacher: this.getTeacherProviderData(),
            student: this.getStudentProviderData(),
            evaluationMode: this.evaluationMode,
            criteriaList: this.evaluationCriteriaList,
            inputs: this.inputs,
            outputs: this.outputs,
        };
        const payload = {
            data: this.nodesData,
            settings: optimizationSettings,
            trainingData: this.trainingData || {},
        };
        this.payload = payload;
    }
    endTraining() {
        this.isTrainingActive = false;
        this.emit('CHANGE_TRAINING_STATE', this.isTrainingActive);
    }
    togglePredict() {
        this.isPredictVisible = !this.isPredictVisible;
        this.emit('CHANGE_PREDICT_VISIBLE', this.isPredictVisible);
    }
    saveTrainingData(data, inputFields, outputFields) {
        this.trainingData = data;
        this.inputs = inputFields;
        this.outputs = outputFields;
    }
    resetState() {
        if (this.modelId) {
            DataProcessingWorker.deallocateModels([this.modelId], WEBWORKER_ROUTES_ENUM.STORE_DEALLOCATE);
        }
        this.providers = getProviders();
        this.availableModels = initialState.availableModels;
        this.isSettingsOpened = initialState.isSettingsOpened;
        this.openedProviderSettings = initialState.openedProviderSettings;
        this.isOptimizationOpened = initialState.isOptimizationOpened;
        this.teacherModel = initialState.teacherModel;
        this.studentModel = initialState.studentModel;
        this.evaluationMode = initialState.evaluationMode;
        this.evaluationCriteriaList = initialState.evaluationCriteriaList;
        this.nodesData = initialState.nodesData;
        this.payload = initialState.payload;
        this.isTrainingActive = initialState.isTrainingActive;
        this.isPredictVisible = initialState.isPredictVisible;
        this.modelId = initialState.modelId;
        this.taskDescription = initialState.taskDescription;
        this.trainingData = initialState.trainingData;
        this.predictionFields = initialState.predictionFields;
    }
    getConnectedProviders() {
        return this.providers.filter((provider) => {
            if (provider.disabled)
                return false;
            return provider.status === ProviderStatus.connected;
        });
    }
    downloadModel() {
        if (!this.modelBlob)
            throw new Error('Model not found');
        const timestamp = Date.now();
        const filename = `prompt-optimization_${timestamp}.luml`;
        const url = URL.createObjectURL(this.modelBlob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }
    createFlowFromMetadata(metadata) {
        const nodes = metadata.nodes.map((node, index) => ({
            ...node,
            type: 'custom',
            data: {
                ...node.data,
                icon: this.getNodeIconByNodeType(node.data.type),
                iconColor: this.getNodeIconColorByNodeType(node.data.type),
                showMenu: false,
                fields: node.data.fields.map((field) => ({
                    ...field,
                    handlePosition: this.getFieldHandlePosition(node.data.type, field.variant),
                })),
            },
            selected: false,
        }));
        const edges = metadata.edges.map((edge) => ({
            id: edge.id,
            source: edge.sourceNode,
            target: edge.targetNode,
            sourceHandle: edge.sourceField,
            targetHandle: edge.targetField,
            type: 'custom',
        }));
        return { nodes, edges };
    }
    haveDuplicatedFields() {
        return this.nodesData?.nodes.find((node) => {
            const values = node.data.fields.map((field) => field.value);
            return values.length !== new Set(values).size;
        });
    }
    prepareNodesData(object) {
        const edges = this.getEdgesFromObject(object);
        const nodes = object.nodes.map((node) => {
            const nodeData = node.data;
            const data = {
                fields: this.getFieldsDataFromNodeData(nodeData),
                hint: nodeData.hint,
                type: nodeData.type,
                label: nodeData.label,
            };
            return { ...node, data };
        });
        this.nodesData = { edges, nodes };
    }
    getEdgesFromObject(object) {
        return object.edges.map((edge) => ({
            id: edge.id,
            sourceNode: edge.source,
            sourceField: edge.sourceHandle,
            targetNode: edge.target,
            targetField: edge.targetHandle,
        }));
    }
    getFieldsDataFromNodeData(nodeData) {
        return nodeData.fields.map((field) => ({
            id: field.id,
            value: field.value,
            variant: field.variant,
            type: field.type,
            variadic: !!field.variadic,
        }));
    }
    getTeacherProviderData() {
        if (!this.teacherModel)
            throw new Error('Select teacher model before');
        const teacherProviderId = allModels.find((item) => item.items.find((model) => model.id === this.teacherModel))?.providerId;
        const teacherProvider = this.providers.find((p) => p.id === teacherProviderId);
        if (teacherProvider?.status === ProviderStatus.disconnected) {
            throw new Error(`Provider "${teacherProvider.name}" is not connected. Please check your API key.`);
        }
        const teacherProviderSettings = teacherProviderId
            ? this.getProviderSettings(teacherProviderId)
            : null;
        const settingsObject = parseProviderSettingsToObject(teacherProviderSettings);
        return {
            providerId: teacherProviderId,
            modelId: this.teacherModel,
            providerSettings: settingsObject,
        };
    }
    getStudentProviderData() {
        if (!this.studentModel)
            throw new Error('Select student model before');
        const studentProviderId = allModels.find((item) => item.items.find((model) => model.id === this.studentModel))?.providerId;
        const studentProvider = this.providers.find((p) => p.id === studentProviderId);
        if (studentProvider?.status === ProviderStatus.disconnected) {
            throw new Error(`Provider "${studentProvider.name}" is not connected. Please check your API key.`);
        }
        const studentProviderSettings = studentProviderId
            ? this.getProviderSettings(studentProviderId)
            : null;
        const settingsObject = parseProviderSettingsToObject(studentProviderSettings);
        return {
            providerId: studentProviderId,
            modelId: this.studentModel,
            providerSettings: settingsObject,
        };
    }
    setModelId(modelId) {
        this.modelId = modelId;
        this.emit('CHANGE_MODEL_ID', this.modelId);
    }
    savePredictionFields() {
        if (!this.nodesData)
            throw new Error('Create nodes data first');
        const fields = this.nodesData.nodes.reduce((acc, node) => {
            node.data.fields.forEach((field) => {
                if (field.variant === 'input' && node.data.type === NodeTypeEnum.input)
                    acc.push(field.value);
            });
            return acc;
        }, []);
        if (fields.length) {
            this.predictionFields = fields;
            this.emit('CHANGE_PREDICTION_FIELDS', this.predictionFields);
        }
    }
    saveModel(model) {
        if (!model)
            throw new Error('Model not found');
        const modelBytes = new Uint8Array(Object.values(model));
        this.modelBlob = new Blob([modelBytes]);
    }
    getNodeIconByNodeType(nodeType) {
        switch (nodeType) {
            case NodeTypeEnum.gate:
                return 'gate';
            case NodeTypeEnum.input:
                return 'input';
            case NodeTypeEnum.output:
                return 'output';
            case NodeTypeEnum.processor:
                return 'cpu';
            default:
                throw new Error('Invalid node type');
        }
    }
    getNodeIconColorByNodeType(nodeType) {
        switch (nodeType) {
            case NodeTypeEnum.gate:
                return 'var(--p-badge-success-background)';
            case NodeTypeEnum.input:
                return 'var(--p-primary-color)';
            case NodeTypeEnum.output:
                return 'var(--p-primary-color)';
            case NodeTypeEnum.processor:
                return 'var(--p-badge-warn-background)';
            default:
                throw new Error('Invalid node type');
        }
    }
    getFieldHandlePosition(nodeType, inputVariant) {
        if (nodeType === NodeTypeEnum.gate) {
            return inputVariant === 'condition' ? Position.Right : Position.Left;
        }
        else if (nodeType === NodeTypeEnum.processor) {
            return inputVariant === 'input' ? Position.Left : Position.Right;
        }
        else if (nodeType === NodeTypeEnum.input) {
            return Position.Right;
        }
        else if (nodeType === NodeTypeEnum.output) {
            return Position.Left;
        }
        else {
            throw new Error('Invalid node type');
        }
    }
}
export const promptFusionService = new PromptFusionServiceClass();
