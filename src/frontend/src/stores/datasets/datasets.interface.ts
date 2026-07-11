import type { Subset } from '@/lib/api/artifacts/interfaces'

export interface SubsetInfo {
  name: string
  subset: Subset
  num_rows: number
}
