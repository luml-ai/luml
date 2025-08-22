import type { MlModel } from '@/lib/api/orbit-ml-models/interfaces'
import { ModelDownloader } from '@/lib/bucket-service'
import { FnnxService } from '@/lib/fnnx/FnnxService'
import {
  ExperimentSnapshotDatabaseProvider,
  type ModelSnapshot,
} from '@/modules/experiment-snapshot'
import { useModelsStore } from '@/stores/models'
import JSZip from 'jszip'
import { ref } from 'vue'
import { useSqlLite } from './useSqlLite'

export const useExperimentSnapshotsDatabaseProvider = () => {
  const modelsStore = useModelsStore()
  const { getSQL, initSql } = useSqlLite()

  const databasesList = ref<ModelSnapshot[]>([])

  async function init(models: MlModel[]) {
    await Promise.all(models.map((model) => addModelDatabase(model)))
    const provider = new ExperimentSnapshotDatabaseProvider(databasesList.value)
    modelsStore.setExperimentSnapshotProvider(provider)
  }

  async function addModelDatabase(model: MlModel) {
    try {
      const buffer = await loadArchiveBuffer(model)
      const db = await createDatabase(buffer)
      databasesList.value.push({ modelId: model.id, database: db })
    } catch (e) {
      console.error(e)
    }
  }

  async function loadArchiveBuffer(model: MlModel) {
    const archiveName = FnnxService.findExperimentSnapshotArchiveName(model.file_index)
    if (!archiveName)
      throw new Error(`Experiment snapshot data for model '${model.model_name}' was not found`)
    const url = await modelsStore.getDownloadUrl(model.id)
    const modelDownloader = new ModelDownloader(url)
    return modelDownloader.getFileFromBucket<ArrayBuffer>(model.file_index, archiveName, true)
  }

  async function createDatabase(buffer: ArrayBuffer) {
    const zip = await JSZip.loadAsync(buffer)
    const dbFile = zip.file('exp.db')
    if (!dbFile) throw new Error('Database file not found')
    const content = await dbFile.async('uint8array')
    await initSql()
    return new getSQL.value.Database(content)
  }

  return {
    init,
  }
}
