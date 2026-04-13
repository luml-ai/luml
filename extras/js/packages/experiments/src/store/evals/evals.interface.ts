import type { GetEvalsByDatasetParams } from '@experiments/interfaces/interfaces'

export type InitialDatasetParamsType = Omit<GetEvalsByDatasetParams, 'dataset_id'>
