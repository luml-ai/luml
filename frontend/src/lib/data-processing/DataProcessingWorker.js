import { WEBWORKER_ROUTES_ENUM, WebworkerMessage, } from './interfaces';
class DataProcessingWorkerClass {
    callbacks = [];
    callbackId = 1;
    constructor() { }
    async sendMessage(message, route, data) {
        const callbackId = this.callbackId++;
        return new Promise((resolve, reject) => {
            this.callbacks[callbackId] = (response) => {
                resolve(response);
            };
            const options = { message, id: callbackId, payload: { route, data } };
            window.pyodideWorker.postMessage(options);
        });
    }
    async initPyodide() {
        if (window.pyodideStartedLoading) {
            return false;
        }
        window.pyodideStartedLoading = true;
        window.pyodideWorker = new Worker('/webworker.js');
        window.pyodideWorker.onmessage = async (event) => {
            const m = event.data;
            const callback = this.callbacks[m.id];
            delete this.callbacks[m.id];
            if (callback)
                callback(m.payload);
        };
        return true;
    }
    saveModel(modelBlob, fileName) {
        const url = URL.createObjectURL(modelBlob);
        const a = document.createElement('a');
        a.href = url;
        a.download = fileName;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }
    async checkPyodideReady() {
        const pyodideReady = await this.sendMessage(WebworkerMessage.LOAD_PYODIDE);
        if (!pyodideReady)
            throw new Error('Webworker is not ready');
    }
    async startTraining(data, route) {
        this.checkPyodideReady();
        const result = await this.sendMessage(WebworkerMessage.INVOKE_ROUTE, route, data);
        return result;
    }
    async startPredict(data, route) {
        this.checkPyodideReady();
        const predictResult = await this.sendMessage(WebworkerMessage.INVOKE_ROUTE, route, data);
        return predictResult;
    }
    async deallocateModels(models, route) {
        const promises = models.map((model_id) => this.sendMessage(WebworkerMessage.INVOKE_ROUTE, route, { model_id }));
        return Promise.all(promises);
    }
    async interrupt() {
        await this.sendMessage(WebworkerMessage.INTERRUPT);
    }
    async initPythonModel(model) {
        this.checkPyodideReady();
        return this.sendMessage(WebworkerMessage.INVOKE_ROUTE, WEBWORKER_ROUTES_ENUM.PYFUNC_INIT, {
            model,
        });
    }
    async computePythonModel(payload) {
        this.checkPyodideReady();
        return this.sendMessage(WebworkerMessage.INVOKE_ROUTE, WEBWORKER_ROUTES_ENUM.PYFUNC_COMPUTE, JSON.parse(JSON.stringify(payload)));
    }
    deinitPythonModel(modelId) {
        return this.sendMessage(WebworkerMessage.INVOKE_ROUTE, WEBWORKER_ROUTES_ENUM.PYFUNC_DEINIT, {
            modelId,
        });
    }
}
export const DataProcessingWorker = new DataProcessingWorkerClass();
