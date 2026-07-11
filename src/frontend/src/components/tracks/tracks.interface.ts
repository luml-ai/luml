import type { ArtifactTypeEnum } from '@/lib/api/artifacts/interfaces'

export interface TrackCardProps {
  date: string
  type: ArtifactTypeEnum.dataset | ArtifactTypeEnum.experiment | ArtifactTypeEnum.model
  artifactsCount: number
  id: string
  name: string
  description: string | undefined
  stages: string[]
}

export interface TrackBreadcrumbsProps {
  trackName: string
  trackId: string
}
