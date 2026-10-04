import type { ArtifactTypeEnum } from '@/lib/api/artifacts/interfaces'
import type { TrackStage } from '@/lib/api/orbit-tracks/interfaces'

export interface TrackCardProps {
  type: ArtifactTypeEnum.dataset | ArtifactTypeEnum.experiment | ArtifactTypeEnum.model
  artifactsCount: number
  id: string
  name: string
  description: string | undefined
  stages: TrackStage[]
  createdAt: string
  updatedAt: string | null
  tags: string[]
}

export interface TrackBreadcrumbsProps {
  trackName: string
  trackId: string
}
