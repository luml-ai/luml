/// <reference lib="webworker" />
import { ExperimentSnapshotDatabaseProvider } from '@luml/experiments';
let provider = null;
const activeRequests = new Set();
async function init(payload, requestId) {
    provider = new ExperimentSnapshotDatabaseProvider();
    await provider.init({ modelsInfo: payload, wasmUrl: '/sql-wasm.wasm' });
    self.postMessage({ type: 'result', requestId, data: true });
}
async function call(payload, requestId) {
    const { method, args } = payload;
    if (!provider) {
        throw new Error('Provider not initialized');
    }
    const fn = provider[method];
    if (typeof fn !== 'function') {
        throw new Error(`Provider method "${method}" does not exist`);
    }
    const result = await fn.apply(provider, args ?? []);
    if (!activeRequests.has(requestId))
        return;
    self.postMessage({ type: 'result', requestId, data: result });
}
self.onmessage = async (event) => {
    const { type, payload, requestId } = event.data;
    activeRequests.add(requestId);
    try {
        switch (type) {
            case 'init':
                await init(payload, requestId);
                break;
            case 'call':
                await call(payload, requestId);
                break;
            case 'cancel':
                activeRequests.delete(requestId);
                break;
        }
    }
    catch (err) {
        activeRequests.delete(requestId);
        self.postMessage({
            type: 'error',
            requestId,
            error: err.message,
        });
    }
};
