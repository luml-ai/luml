import axios from 'axios'
import type { MlModel } from '../api/orbit-ml-models/interfaces'

export class ModelDownloader {
  url: string

  constructor(url: string) {
    this.url = url
  }

  async getFileFromBucket(model: MlModel, fileName: string, buffer?: boolean, outerOffset = 0) {
    const range = this.getRangeHeader(model, fileName, outerOffset)
    const file = await axios.get(this.url, {
      headers: { Range: range },
      responseType: buffer ? 'arraybuffer' : 'json',
    })
    return file.data
  }

  getRangeHeader(model: MlModel, fileName: string, outerOffset = 0) {
    const range = model.file_index[fileName]
    if (!range) throw new Error('Model not include this file')
    const start = range[0] + outerOffset
    const end = start + range[1] - 1
    return `bytes=${start}-${end}`
  }
}
