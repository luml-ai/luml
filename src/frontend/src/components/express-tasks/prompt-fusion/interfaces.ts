import { Position, type Node } from '@vue-flow/core'
import {
  CaseUpper,
  Hash,
  Braces,
  CircleArrowDown,
  CircleArrowUp,
  Cpu,
  BetweenHorizonalStart,
} from 'lucide-vue-next'
import type { FunctionalComponent } from 'vue'

export const PROMPT_FIELDS_ICONS: Record<string, FunctionalComponent> = {
  string: CaseUpper,
  integer: Hash,
  float: Hash,
  complex: Braces,
}

export const PROMPT_NODES_ICONS = {
  input: CircleArrowDown,
  cpu: Cpu,
  gate: BetweenHorizonalStart,
  output: CircleArrowUp,
}

export enum NodeTypeEnum {
  input = 'input',
  gate = 'gate',
  processor = 'processor',
  output = 'output',
}

export enum PromptFieldTypeEnum {
  string = 'String',
  integer = 'Integer',
  float = 'Float',
  complex = 'Complex',
}

export interface PromptNode extends Node {
  type: 'custom'
  data: NodeData
  selected: boolean
}

export interface NodeData {
  label: string
  icon: keyof typeof PROMPT_NODES_ICONS
  iconColor: NodeIconColor
  fields: NodeField[]
  showMenu: boolean
  hint?: string
  type: NodeTypeEnum
}

export interface NodeField {
  id: string
  value: string
  handlePosition: Position.Left | Position.Right
  variant: FieldVariant
  type?: PromptFieldTypeEnum
  variadic?: boolean
}

export type FieldVariant = 'input' | 'output' | 'condition'

type NodeIconColor =
  | 'var(--p-primary-color)'
  | 'var(--p-badge-warn-background)'
  | 'var(--p-badge-success-background)'
