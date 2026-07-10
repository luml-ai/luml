/**
 * Span helpers for the trace viewer.
 *
 * Ported from the Platform's experiment-snapshot viewer so the Satellite dashboard
 * renders traces identically: same tree construction from `parent_span_id`, same
 * duration formatting, same icon-per-span-type mapping.
 */
import { Bot, Circle, MessageSquareMore, Ruler, Shuffle, Wrench } from 'lucide-vue-next'
import type { Component } from 'vue'
import { SpanTypeEnum, type TraceSpan, type TraceSpanNode } from '@/api/types'

export interface SpanTypeData {
  icon: Component
  color: string
}

export function getSpanTypeData(type: SpanTypeEnum | null): SpanTypeData {
  switch (type) {
    case SpanTypeEnum.AGENT:
      return { icon: Bot, color: 'var(--luml-span-icon-6)' }
    case SpanTypeEnum.CHAT:
      return { icon: MessageSquareMore, color: 'var(--luml-span-icon-2)' }
    case SpanTypeEnum.TOOL:
      return { icon: Wrench, color: 'var(--luml-span-icon-3)' }
    case SpanTypeEnum.EMBEDDER:
      return { icon: Ruler, color: 'var(--luml-span-icon-4)' }
    case SpanTypeEnum.RERANKER:
      return { icon: Shuffle, color: 'var(--luml-span-icon-5)' }
    default:
      return { icon: Circle, color: 'var(--luml-span-icon-1)' }
  }
}

export function getFormattedExecutionTime(ns: number): string {
  if (ns < 1_000) return `${ns}ns`

  const ms = ns / 1_000_000
  if (ms < 1000) return `${ms.toFixed()}ms`

  const seconds = ms / 1000
  if (seconds < 60) return `${seconds.toFixed(2)}s`

  const minutes = Math.floor(seconds / 60)
  const remainingSec = Math.floor(seconds % 60)
  return `${minutes}m ${remainingSec}s`
}

export function getFormattedTime(startNs: number, endNs: number): string {
  return getFormattedExecutionTime(endNs - startNs)
}

/** Nest spans by `parent_span_id`; spans whose parent is missing become roots. */
export function buildSpanTree(spans: TraceSpan[]): TraceSpanNode[] {
  const spanMap: Record<string, TraceSpanNode> = {}
  for (const span of spans) {
    spanMap[span.span_id] = { ...span, children: [] }
  }

  const roots: TraceSpanNode[] = []
  for (const span of Object.values(spanMap)) {
    const parent = span.parent_span_id ? spanMap[span.parent_span_id] : undefined
    if (parent) parent.children.push(span)
    else roots.push(span)
  }
  return sortSpans(roots)
}

/** Chronological order, depth-first — the order the waterfall reads in. */
function sortSpans(spans: TraceSpanNode[]): TraceSpanNode[] {
  spans.sort((a, b) => a.start_time_unix_nano - b.start_time_unix_nano)
  for (const span of spans) sortSpans(span.children)
  return spans
}

/** The trace's own time bounds, so every bar is drawn on one shared scale. */
export function spanTimeBounds(spans: TraceSpan[]): { min: number; max: number } {
  if (!spans.length) return { min: 0, max: 0 }
  return {
    min: Math.min(...spans.map((s) => s.start_time_unix_nano)),
    max: Math.max(...spans.map((s) => s.end_time_unix_nano)),
  }
}

