import type { GetEvalsByDatasetParams } from '@/interfaces/interfaces'

export type InitialDatasetParamsType = Omit<GetEvalsByDatasetParams, 'dataset_id'>
