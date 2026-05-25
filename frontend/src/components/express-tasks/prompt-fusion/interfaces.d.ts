import { Position, type Node } from '@vue-flow/core';
import type { FunctionalComponent } from 'vue';
export declare const PROMPT_FIELDS_ICONS: Record<string, FunctionalComponent>;
export declare const PROMPT_NODES_ICONS: {
    input: any;
    cpu: any;
    gate: any;
    output: any;
};
export declare enum NodeTypeEnum {
    input = "input",
    gate = "gate",
    processor = "processor",
    output = "output"
}
export declare enum PromptFieldTypeEnum {
    string = "String",
    integer = "Integer",
    float = "Float",
    complex = "Complex"
}
export interface PromptNode extends Node {
    type: 'custom';
    data: NodeData;
    selected: boolean;
}
export interface NodeData {
    label: string;
    icon: keyof typeof PROMPT_NODES_ICONS;
    iconColor: NodeIconColor;
    fields: NodeField[];
    showMenu: boolean;
    hint?: string;
    type: NodeTypeEnum;
}
export interface NodeField {
    id: string;
    value: string;
    handlePosition: Position.Left | Position.Right;
    variant: FieldVariant;
    type?: PromptFieldTypeEnum;
    variadic?: boolean;
}
export type FieldVariant = 'input' | 'output' | 'condition';
type NodeIconColor = 'var(--p-primary-color)' | 'var(--p-badge-warn-background)' | 'var(--p-badge-success-background)';
export {};
