import { type PromptNode } from '@/components/express-tasks/prompt-fusion/interfaces';
export declare const getEmptyGateNode: () => PromptNode;
export declare const getEmptyProcessorNode: () => PromptNode;
export declare const getInputNode: (fields?: string[]) => PromptNode;
export declare const getOutputNode: (fields?: string[]) => PromptNode;
export declare const getInitialNodes: (inputFields?: string[], outputFields?: string[]) => PromptNode[];
export declare const getSample: (inputs?: string[], outputs?: string[]) => {
    nodes: PromptNode[];
    edges: Edge[];
};
