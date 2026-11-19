import type { Component } from 'vue'

export interface SpanTypeData {
  icon: Component
  color: string
}

export interface TraceSpanRange {
  min: number | null
  max: number | null
}

export interface TraceEntry {
  key: string
  value: unknown
}
