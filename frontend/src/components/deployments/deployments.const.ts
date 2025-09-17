import type { DialogPassThroughOptions } from 'primevue'

export const dialogPt: DialogPassThroughOptions = {
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
}

export const editorDialogPt: DialogPassThroughOptions = {
  footer: {
    style: 'display: flex; justify-content: space-between; width: 100%; margin-top: auto;',
  },
}

export const getInitialFormData = (collectionId?: number, modelId?: number) => {
  return {
    name: '',
    description: '',
    tags: [],
    collectionId: collectionId,
    modelId: modelId,
    satelliteId: null,
    secretDynamicAttributes: [],
    dynamicAttributes: [],
    secretEnvs: [],
    notSecretEnvs: [],
    customVariables: [],
    satelliteFields: [],
  }
}
