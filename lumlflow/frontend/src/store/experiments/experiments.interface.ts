export interface Experiment {
  id: string
  name: string
  description: string
  created_at: string
  tags: string[]
  duration: number
  source: string
  models: { id: string; name: string }[]
  metrics: Record<string, number>
  status: 'active' | 'completed' | 'failed'
}

export interface UpdateExperimentPayload {
  name?: string
  description?: string
  tags?: string[]
}
