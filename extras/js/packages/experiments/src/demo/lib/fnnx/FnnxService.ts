import { Model } from '@fnnx/web'

interface ModelFile {
  relpath: string
  content: Uint8Array
}

class FnnxServiceClass {
  async createModelFromFile(file: File) {
    const allowedExtensions = ['.fnnx', '.pyfnx', '.dfs', '.luml']
    if (!allowedExtensions.some((ext) => file.name.endsWith(ext))) {
      throw new Error('Incorrect file format')
    }
    const buffer = await file.arrayBuffer()
    const model = await Model.fromBuffer(buffer)
    return model
  }

  findExperimentSnapshotArchive(files: ModelFile[]) {
    const regex =
      /meta_artifacts\/dataforce\.studio~c~~c~experiment_snapshot~c~v1~~et~~[^/]+\/exp\.db\.zip$/

    return files.find((file) => regex.test(file.relpath))?.content
  }
}

export const FnnxService = new FnnxServiceClass()
