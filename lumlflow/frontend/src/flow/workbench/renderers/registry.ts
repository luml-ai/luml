import type { Component } from 'vue'
import type { AssetKind, PreviewValue } from '../model/types'
import BlocksRenderer from './BlocksRenderer.vue'
import DatasetRenderer from './DatasetRenderer.vue'
import EvalRenderer from './EvalRenderer.vue'
import ExperimentRenderer from './ExperimentRenderer.vue'
import FileRenderer from './FileRenderer.vue'
import FrameRenderer from './FrameRenderer.vue'
import KvRenderer from './KvRenderer.vue'
import MetricRenderer from './MetricRenderer.vue'
import ModelRenderer from './ModelRenderer.vue'
import NoteRenderer from './NoteRenderer.vue'
import PlotRenderer from './PlotRenderer.vue'
import TextRenderer from './TextRenderer.vue'

const RENDERERS: Partial<Record<AssetKind, Component>> = {
  frame: FrameRenderer,
  plot: PlotRenderer,
  metric: MetricRenderer,
  note: NoteRenderer,
  eval: EvalRenderer,
  model: ModelRenderer,
  dataset: DatasetRenderer,
  experiment: ExperimentRenderer,
  checkpoint: FileRenderer,
  file: FileRenderer,
  image: FileRenderer,
  text: TextRenderer,
  html: TextRenderer,
}

export function rendererFor(kind: AssetKind): Component {
  return RENDERERS[kind] ?? KvRenderer
}

const KIND_OF_PREVIEW: Record<Exclude<PreviewValue['type'], 'blocks'>, AssetKind> = {
  frame: 'frame',
  plot: 'plot',
  metric: 'metric',
  note: 'note',
  model: 'model',
  experiment: 'experiment',
  eval: 'eval',
  dataset: 'dataset',
  file: 'checkpoint',
  text: 'text',
  kv: 'unknown',
}

export function rendererForPreview(preview: PreviewValue): Component {
  if (preview.type === 'blocks') return BlocksRenderer
  return rendererFor(KIND_OF_PREVIEW[preview.type] ?? 'unknown')
}
