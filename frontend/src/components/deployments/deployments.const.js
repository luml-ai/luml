export const dialogPt = {
    mask: {
        style: 'padding: 88px 0 40px;',
    },
    root: {
        style: 'width: calc(100% - 32px); height: 100%; max-height: none;',
    },
    header: {
        style: 'padding: 16px 20px; text-transform: uppercase; font-size: 20px; font-weight: 600;',
    },
    content: {
        style: 'padding: 0',
    },
    headerActions: {
        style: 'display: none;',
    },
};
export const editorDialogPt = {
    footer: {
        style: 'display: flex; justify-content: space-between; width: 100%; margin-top: auto;',
    },
};
export const deploymentErrorDialogPt = {
    root: {
        style: 'max-width: calc(100% - 32px); padding: 13px 6px 6px; min-width: 320px;',
    },
    header: {
        style: 'padding: 16px 20px; text-transform: uppercase; font-size: 16px; font-weight: 500;',
    },
    footer: {
        style: 'justify-content: flex-start;',
    },
};
export const getInitialFormData = (collectionId, modelId) => {
    return {
        name: '',
        description: '',
        tags: [],
        collectionId: collectionId ?? '',
        modelId: modelId ?? '',
        satelliteId: '',
        secretDynamicAttributes: [],
        dynamicAttributes: [],
        secretEnvs: [],
        notSecretEnvs: [],
        customVariables: [],
        satelliteFields: [],
    };
};
