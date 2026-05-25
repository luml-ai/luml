import type { DialogPassThroughOptions } from 'primevue';
import type { CreateDeploymentForm } from './deployments.interfaces';
export declare const dialogPt: DialogPassThroughOptions;
export declare const editorDialogPt: DialogPassThroughOptions;
export declare const deploymentErrorDialogPt: DialogPassThroughOptions;
export declare const getInitialFormData: (collectionId?: string, modelId?: string) => CreateDeploymentForm;
