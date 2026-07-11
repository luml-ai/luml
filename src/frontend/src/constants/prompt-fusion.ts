import {
  NodeTypeEnum,
  PromptFieldTypeEnum,
  type PromptNode,
} from '@/components/express-tasks/prompt-fusion/interfaces'
import { Position, type Edge } from '@vue-flow/core'
import { v4 as uuidv4 } from 'uuid'

export const getEmptyGateNode = (): PromptNode => ({
  id: uuidv4(),
  type: 'custom',
  data: {
    label: 'Gate',
    icon: 'gate',
    iconColor: 'var(--p-badge-success-background)',
    fields: [
      { id: uuidv4(), value: '', handlePosition: Position.Left, variant: 'output' },
      { id: uuidv4(), value: '', handlePosition: Position.Right, variant: 'condition' },
      { id: uuidv4(), value: '', handlePosition: Position.Right, variant: 'condition' },
    ],
    showMenu: true,
    hint: '',
    type: NodeTypeEnum.gate,
  },
  position: { x: 20, y: 20 },
  selected: false,
})

export const getEmptyProcessorNode = (): PromptNode => ({
  id: uuidv4(),
  type: 'custom',
  data: {
    label: 'Processor',
    icon: 'cpu',
    iconColor: 'var(--p-badge-warn-background)',
    fields: [
      { id: uuidv4(), value: '', handlePosition: Position.Left, variant: 'input' },
      { id: uuidv4(), value: '', handlePosition: Position.Right, variant: 'output' },
    ],
    showMenu: true,
    hint: '',
    type: NodeTypeEnum.processor,
  },
  position: { x: 20, y: 20 },
  selected: false,
})

export const getInputNode = (fields?: string[]): PromptNode => {
  return {
    id: uuidv4(),
    type: 'custom',
    data: {
      label: 'Input',
      icon: 'input',
      iconColor: 'var(--p-primary-color)',
      fields: fields
        ? fields.map((field) => ({
            id: uuidv4(),
            value: field,
            handlePosition: Position.Right,
            variant: 'input',
          }))
        : [{ id: uuidv4(), value: '', handlePosition: Position.Right, variant: 'input' }],
      showMenu: false,
      type: NodeTypeEnum.input,
    },
    position: { x: 20, y: 20 },
    selected: false,
  }
}

export const getOutputNode = (fields?: string[]): PromptNode => {
  return {
    id: uuidv4(),
    type: 'custom',
    data: {
      label: 'Output',
      icon: 'output',
      iconColor: 'var(--p-primary-color)',
      fields: fields
        ? fields.map((field) => ({
            id: uuidv4(),
            value: field,
            handlePosition: Position.Left,
            variant: 'output',
          }))
        : [{ id: uuidv4(), value: '', handlePosition: Position.Left, variant: 'output' }],
      showMenu: false,
      type: NodeTypeEnum.output,
    },
    position: { x: 20, y: 20 },
    selected: false,
  }
}

export const getInitialNodes = (inputFields?: string[], outputFields?: string[]) => {
  const inputNode = structuredClone(getInputNode(inputFields))
  const outputNode = structuredClone(getOutputNode(outputFields))
  inputNode.position = { x: 100, y: 200 }
  outputNode.position = { x: 1000, y: 200 }
  return [inputNode, outputNode]
}

export const getSample = (inputs?: string[], outputs?: string[]) => {
  const edges: Edge[] = []
  const nodes: PromptNode[] = []

  const inputNode = getInputNode()
  const inputNodeId = inputNode.id
  const inputNodeFieldId = uuidv4()
  inputNode.data.fields = [
    {
      id: inputNodeFieldId,
      value: inputs?.[0] ? inputs[0] : 'text',
      handlePosition: Position.Right,
      variant: 'input',
      type: 'string' as PromptFieldTypeEnum,
    },
  ]
  inputNode.position = { x: 100, y: 200 }

  const firstGate = getEmptyGateNode()
  const firstGateId = firstGate.id
  const firstGateFirstInputId = uuidv4()
  const firstGateSecondInputId = uuidv4()
  const firstGateThirdInputId = uuidv4()
  firstGate.data.hint = 'Determine language'
  firstGate.data.fields = [
    { id: firstGateFirstInputId, value: 'text', handlePosition: Position.Left, variant: 'output' },
    {
      id: firstGateSecondInputId,
      value: 'EN text',
      handlePosition: Position.Right,
      variant: 'condition',
    },
    {
      id: firstGateThirdInputId,
      value: 'non EN text',
      handlePosition: Position.Right,
      variant: 'condition',
    },
  ]
  firstGate.position = { x: 400, y: 100 }

  const secondGate = getEmptyGateNode()
  const secondGateId = secondGate.id
  const secondGateFirstInputId = uuidv4()
  const secondGateSecondInputId = uuidv4()
  const secondGateThirdInputId = uuidv4()
  secondGate.data.hint = 'Determine if formal'
  secondGate.data.fields = [
    {
      id: secondGateFirstInputId,
      value: 'en_text',
      handlePosition: Position.Left,
      variant: 'output',
    },
    {
      id: secondGateSecondInputId,
      value: 'formal',
      handlePosition: Position.Right,
      variant: 'condition',
    },
    {
      id: secondGateThirdInputId,
      value: 'informal',
      handlePosition: Position.Right,
      variant: 'condition',
    },
  ]
  secondGate.position = { x: 700, y: 100 }

  const firstProcessor = getEmptyProcessorNode()
  const firstProcessorId = firstProcessor.id
  const firstProcessorFirstInputId = uuidv4()
  const firstProcessorSecondInputId = uuidv4()
  firstProcessor.data.hint = 'Translate into EN'
  firstProcessor.data.fields = [
    {
      id: firstProcessorFirstInputId,
      value: 'text',
      handlePosition: Position.Left,
      variant: 'input',
    },
    {
      id: firstProcessorSecondInputId,
      value: 'en_text',
      handlePosition: Position.Right,
      variant: 'output',
      type: 'string' as PromptFieldTypeEnum,
    },
  ]
  firstProcessor.position = { x: 400, y: 300 }

  const secondProcessor = getEmptyProcessorNode()
  const secondProcessorId = secondProcessor.id
  const secondProcessorFirstInputId = uuidv4()
  const secondProcessorSecondInputId = uuidv4()
  secondProcessor.data.hint = 'Make formal'
  secondProcessor.data.fields = [
    {
      id: secondProcessorFirstInputId,
      value: 'en_text',
      handlePosition: Position.Left,
      variant: 'input',
    },
    {
      id: secondProcessorSecondInputId,
      value: 'formal_text',
      handlePosition: Position.Right,
      variant: 'output',
      type: 'string' as PromptFieldTypeEnum,
    },
  ]
  secondProcessor.position = { x: 700, y: 300 }

  const outputNode = getOutputNode()
  const outputNodeId = outputNode.id
  const outputNodeFieldId = uuidv4()
  outputNode.data.fields = [
    {
      id: outputNodeFieldId,
      value: outputs?.[0] ? outputs[0] : 'formal_text',
      handlePosition: Position.Left,
      variant: 'output',
    },
  ]
  outputNode.position = { x: 1000, y: 200 }

  nodes.push(inputNode, firstGate, secondGate, firstProcessor, secondProcessor, outputNode)
  edges.push(
    {
      id: uuidv4(),
      source: inputNodeId,
      sourceHandle: inputNodeFieldId,
      target: firstGateId,
      targetHandle: firstGateFirstInputId,
      type: 'custom',
    },
    {
      id: uuidv4(),
      source: firstGateId,
      sourceHandle: firstGateSecondInputId,
      target: secondGateId,
      targetHandle: secondGateFirstInputId,
      type: 'custom',
    },
    {
      id: uuidv4(),
      source: firstGateId,
      sourceHandle: firstGateThirdInputId,
      target: firstProcessorId,
      targetHandle: firstProcessorFirstInputId,
      type: 'custom',
    },
    {
      id: uuidv4(),
      source: firstProcessorId,
      sourceHandle: firstProcessorSecondInputId,
      target: secondGateId,
      targetHandle: secondGateFirstInputId,
      type: 'custom',
    },
    {
      id: uuidv4(),
      source: secondGateId,
      sourceHandle: secondGateSecondInputId,
      target: outputNodeId,
      targetHandle: outputNodeFieldId,
      type: 'custom',
    },
    {
      id: uuidv4(),
      source: secondGateId,
      sourceHandle: secondGateThirdInputId,
      target: secondProcessorId,
      targetHandle: secondProcessorFirstInputId,
      type: 'custom',
    },
    {
      id: uuidv4(),
      source: secondProcessorId,
      sourceHandle: secondProcessorSecondInputId,
      target: outputNodeId,
      targetHandle: outputNodeFieldId,
      type: 'custom',
    },
  )

  return { nodes, edges }
}
