const FILE_TYPES = {
  model: ['dfs', 'fnnx', 'pyfnx', 'luml'],
  experiment: ['luml'],
  dataset: ['tar'],
} as const

export const isCorrectFileName = (fileName: string) => {
  const regex = /^[^:\"*\`~#%;'^]+\.[^\s:\"*\`~#%;'^]+$/
  return regex.test(fileName)
}

export const isModelFile = (fileName: string) => {
  return FILE_TYPES.model.some((type) => fileName.endsWith('.' + type))
}

export const isExperimentFile = (fileName: string) => {
  return FILE_TYPES.experiment.some((type) => fileName.endsWith('.' + type))
}

export const isDatasetFile = (fileName: string) => {
  return FILE_TYPES.dataset.some((type) => fileName.endsWith('.' + type))
}
