import {
  WEBWORKER_ROUTES_ENUM,
  WebworkerMessage,
  type ForecastingPredictRequest,
  type ForecastingTrainPayload,
  type PredictRequestData,
  type PromptOptimizationData,
  type TaskPayload,
} from './interfaces'

class DataProcessingWorkerClass {
  private worker?: Worker
  private initialization: Promise<void> | null = null
  private callbacks = new Map<
    number,
    { resolve: (response: unknown) => void; reject: (error: Error) => void }
  >()
  private callbackId: number = 1

  async sendMessage<T = unknown>(
    message: WebworkerMessage,
    route?: WEBWORKER_ROUTES_ENUM,
    data?: unknown,
  ): Promise<T> {
    await this.initPyodide()
    return this.postMessage<T>(message, route, data)
  }

  private postMessage<T = unknown>(
    message: WebworkerMessage,
    route?: WEBWORKER_ROUTES_ENUM,
    data?: unknown,
  ): Promise<T> {
    const worker = this.worker
    if (!worker) return Promise.reject(new Error('Webworker is not ready'))
    const callbackId = this.callbackId++
    return new Promise<T>((resolve, reject) => {
      this.callbacks.set(callbackId, { resolve: (response) => resolve(response as T), reject })
      try {
        worker.postMessage({ message, id: callbackId, payload: { route, data } })
      } catch (error) {
        this.callbacks.delete(callbackId)
        reject(error)
      }
    })
  }

  initPyodide(): Promise<void> {
    if (!this.initialization) {
      let worker: Worker | undefined
      this.initialization = (async () => {
        worker = new Worker('/webworker.js')
        this.worker = worker
        worker.onmessage = (event) => {
          const message = event.data
          const callback = this.callbacks.get(message.id)
          this.callbacks.delete(message.id)
          if (message.error !== undefined || message.payload?.status === 'error') {
            callback?.reject(
              new Error(
                message.error || message.payload?.error_message || 'Webworker request failed',
              ),
            )
          } else callback?.resolve(message.payload)
        }
        worker.onerror = (event) => {
          this.resetWorker(new Error(event.message || 'Webworker failed'), worker)
        }
        worker.onmessageerror = () => {
          this.resetWorker(new Error('Could not decode webworker response'), worker)
        }
        const timeout = setTimeout(() => {
          this.resetWorker(new Error('Pyodide initialization timed out. Please try again.'), worker)
        }, 120_000)
        try {
          const ready = await this.postMessage<boolean>(WebworkerMessage.LOAD_PYODIDE)
          if (!ready) throw new Error('Webworker is not ready')
        } finally {
          clearTimeout(timeout)
        }
      })().catch((error) => {
        this.resetWorker(error, worker)
        throw error
      })
    }
    return this.initialization
  }

  private resetWorker(error: Error, worker?: Worker) {
    if (worker !== this.worker) return
    this.worker?.terminate()
    this.worker = undefined
    this.initialization = null
    for (const callback of this.callbacks.values()) callback.reject(error)
    this.callbacks.clear()
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

  checkPyodideReady() {
    return this.initPyodide()
  }

  async startTraining<T = unknown>(
    data: TaskPayload | PromptOptimizationData | ForecastingTrainPayload,
    route:
      | WEBWORKER_ROUTES_ENUM.TABULAR_TRAIN
      | WEBWORKER_ROUTES_ENUM.PROMPT_OPTIMIZATION_TRAIN
      | WEBWORKER_ROUTES_ENUM.FORECASTING_TRAIN,
  ): Promise<T> {
    const result = await this.sendMessage<T>(WebworkerMessage.INVOKE_ROUTE, route, data)
    return result
  }

  async startPredict<T = unknown>(
    data: PredictRequestData | ForecastingPredictRequest,
    route:
      | WEBWORKER_ROUTES_ENUM.TABULAR_PREDICT
      | WEBWORKER_ROUTES_ENUM.PROMPT_OPTIMIZATION_PREDICT
      | WEBWORKER_ROUTES_ENUM.FORECASTING_PREDICT,
  ): Promise<T> {
    const predictResult = await this.sendMessage<T>(WebworkerMessage.INVOKE_ROUTE, route, data)
    return predictResult
  }

  async deallocateModels(
    models: string[],
    route:
      | WEBWORKER_ROUTES_ENUM.TABULAR_DEALLOCATE
      | WEBWORKER_ROUTES_ENUM.STORE_DEALLOCATE
      | WEBWORKER_ROUTES_ENUM.FORECASTING_DEALLOCATE,
  ) {
    if (!models.length) return []
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
