import { ModelDownloader } from '@/lib/bucket-service';
import { FnnxService } from '@/lib/fnnx/FnnxService';
import { ExperimentSnapshotWorkerProxy } from '@luml/experiments';
import { useArtifactsStore } from '@/stores/artifacts';
import { onUnmounted } from 'vue';
export const useExperimentSnapshotsDatabaseProvider = () => {
    const artifactsStore = useArtifactsStore();
    let abortControllers = {};
    const worker = new Worker(new URL('@/workers/experiment-snapshot', import.meta.url), {
        type: 'module',
    });
    worker.onerror = (e) => {
        console.error('❌ Worker error:', e);
    };
    worker.onmessageerror = (e) => {
        console.error('❌ Worker message error:', e);
    };
    function callWorker(message) {
        const requestId = crypto.randomUUID();
        return new Promise((resolve, reject) => {
            const handler = (e) => {
                if (e.data.requestId !== requestId)
                    return;
                worker.removeEventListener('message', handler);
                if (e.data.type === 'error') {
                    reject(e.data.error);
                }
                else {
                    resolve(e.data.data);
                }
            };
            worker.addEventListener('message', handler);
            worker.postMessage({ ...message, requestId });
        });
    }
    async function init(models) {
        const payload = await Promise.all(models.map(async (model) => ({
            modelId: model.id,
            buffer: await loadArchiveBuffer(model),
        })));
        await callWorker({
            type: 'init',
            payload,
        });
        const provider = new ExperimentSnapshotWorkerProxy(worker);
        artifactsStore.setExperimentSnapshotProvider(provider);
    }
    async function loadArchiveBuffer(model) {
        abortControllers[model.id]?.abort();
        abortControllers[model.id] = new AbortController();
        const { signal } = abortControllers[model.id];
        const archiveName = FnnxService.findExperimentSnapshotArchiveName(model.file_index);
        if (!archiveName)
            throw new Error(`Experiment snapshot data for model '${model.name}' was not found`);
        const url = await artifactsStore.getDownloadUrl(model.id);
        const modelDownloader = new ModelDownloader(url);
        return modelDownloader.getFileFromBucket(model.file_index, archiveName, true, 0, signal);
    }
    onUnmounted(() => {
        Object.values(abortControllers).forEach((controller) => {
            controller.abort();
        });
    });
    return {
        init,
    };
};
