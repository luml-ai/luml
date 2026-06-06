import {
  WEBWORKER_ROUTES_ENUM,
  WebworkerMessage,
  type PredictRequestData,
  type PromptOptimizationData,
  type TaskPayload,
} from './interfaces'

class DataProcessingWorkerClass {
  private callbacks: Array<(response: unknown) => void> = []
  private callbackId: number = 1

  async sendMessage<T = unknown>(
    message: WebworkerMessage,
    route?: WEBWORKER_ROUTES_ENUM,
    data?: unknown,
  ): Promise<T> {
    const callbackId = this.callbackId++
    return new Promise<T>((resolve) => {
      this.callbacks[callbackId] = (response) => {
        resolve(response as T)
      }
      const options = { message, id: callbackId, payload: { route, data } }
      window.pyodideWorker.postMessage(options)
    })
  }

  async initPyodide() {
    if (window.pyodideStartedLoading) {
      return false
    }
    window.pyodideStartedLoading = true
    window.pyodideWorker = new Worker('/webworker.js')
    window.pyodideWorker.onmessage = async (event) => {
      const m = event.data
      const callback = this.callbacks[m.id]
      // eslint-disable-next-line @typescript-eslint/no-dynamic-delete
      delete this.callbacks[m.id]
      if (callback) callback(m.payload)
    }
    return true
  }

  saveModel(modelBlob: Blob, fileName: string) {
    const url = URL.createObjectURL(modelBlob)
    const a = document.createElement('a')
    a.href = url
    a.download = fileName
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  async checkPyodideReady() {
    const pyodideReady = await this.sendMessage(WebworkerMessage.LOAD_PYODIDE)
    if (!pyodideReady) throw new Error('Webworker is not ready')
  }

  async startTraining<T = unknown>(
    data: TaskPayload | PromptOptimizationData,
    route: WEBWORKER_ROUTES_ENUM.TABULAR_TRAIN | WEBWORKER_ROUTES_ENUM.PROMPT_OPTIMIZATION_TRAIN,
  ): Promise<T> {
    this.checkPyodideReady()
    const result = await this.sendMessage<T>(WebworkerMessage.INVOKE_ROUTE, route, data)
    return result
  }

  async startPredict<T = unknown>(
    data: PredictRequestData,
    route:
      | WEBWORKER_ROUTES_ENUM.TABULAR_PREDICT
      | WEBWORKER_ROUTES_ENUM.PROMPT_OPTIMIZATION_PREDICT,
  ): Promise<T> {
    this.checkPyodideReady()
    const predictResult = await this.sendMessage<T>(WebworkerMessage.INVOKE_ROUTE, route, data)
    return predictResult
  }

  async deallocateModels(
    models: string[],
    route: WEBWORKER_ROUTES_ENUM.TABULAR_DEALLOCATE | WEBWORKER_ROUTES_ENUM.STORE_DEALLOCATE,
  ) {
    const promises = models.map((model_id) =>
      this.sendMessage(WebworkerMessage.INVOKE_ROUTE, route, { model_id }),
    )
    return Promise.all(promises)
  }

  async interrupt() {
    await this.sendMessage(WebworkerMessage.INTERRUPT)
  }

  async initPythonModel(
    model: ArrayBuffer,
  ): Promise<{ model_id: string; status: 'success' } | { status: 'error'; error_message: string }> {
    this.checkPyodideReady()
    return this.sendMessage<
      { model_id: string; status: 'success' } | { status: 'error'; error_message: string }
    >(WebworkerMessage.INVOKE_ROUTE, WEBWORKER_ROUTES_ENUM.PYFUNC_INIT, {
      model,
    })
  }

  async computePythonModel(payload: {
    model_id: string
    inputs: object
    dynamic_attributes: object
  }): Promise<
    | { status: 'success'; predictions: Record<string, Record<string, string>> }
    | { status: 'error'; error_type: string; error_message: string }
  > {
    this.checkPyodideReady()
    return this.sendMessage<
      | { status: 'success'; predictions: Record<string, Record<string, string>> }
      | { status: 'error'; error_type: string; error_message: string }
    >(
      WebworkerMessage.INVOKE_ROUTE,
      WEBWORKER_ROUTES_ENUM.PYFUNC_COMPUTE,
      JSON.parse(JSON.stringify(payload)),
    )
  }

  deinitPythonModel(modelId: string) {
    return this.sendMessage(WebworkerMessage.INVOKE_ROUTE, WEBWORKER_ROUTES_ENUM.PYFUNC_DEINIT, {
      modelId,
    })
  }
}

export const DataProcessingWorker = new DataProcessingWorkerClass()
