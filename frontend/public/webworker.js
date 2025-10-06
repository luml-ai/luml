// webworker
//for debug only
// DRY_RUN = false;

importScripts("https://cdn.jsdelivr.net/pyodide/v0.27.2/full/pyodide.js");
//import { loadPyodide } from "https://cdn.jsdelivr.net/pyodide/v0.27.2/full/pyodide.mjs";

// let pyodide = null;
// let micropip = null;

const MESSAGES = {
    LOAD_PYODIDE: "LOAD_PYODIDE",
};

async function initPyWorker() {
    // if (DRY_RUN) {
    //     return true;
    // }
    const pyodide = await loadPyodide();
    await pyodide.loadPackage("micropip");


    /////////////////////////////////////////

    await pyodide.loadPackage("https://cdn.jsdelivr.net/pyodide/v0.26.2/full/numpy-1.26.4-cp312-cp312-pyodide_2024_0_wasm32.whl");
    await pyodide.loadPackage("https://cdn.jsdelivr.net/pyodide/v0.26.2/full/scikit_learn-1.4.2-cp312-cp312-pyodide_2024_0_wasm32.whl");
    // await pyodide.loadPackage("https://cdn.jsdelivr.net/pyodide/v0.26.2/full/scipy-1.12.0-cp312-cp312-pyodide_2024_0_wasm32.whl");
    // await pyodide.loadPackage("https://cdn.jsdelivr.net/pyodide/v0.26.2/full/openblas-0.3.26.zip");
    await pyodide.loadPackage("https://cdn.jsdelivr.net/pyodide/v0.26.2/full/joblib-1.4.0-py3-none-any.whl");
    await pyodide.loadPackage("https://cdn.jsdelivr.net/pyodide/v0.26.2/full/threadpoolctl-3.4.0-py3-none-any.whl");
    await pyodide.loadPackage("https://cdn.jsdelivr.net/pyodide/v0.26.2/full/protobuf-4.24.4-cp312-cp312-pyodide_2024_0_wasm32.whl");
    await pyodide.loadPackage("https://cdn.jsdelivr.net/pyodide/v0.26.2/full/pandas-2.2.0-cp312-cp312-pyodide_2024_0_wasm32.whl");
    await pyodide.loadPackage("https://cdn.jsdelivr.net/pyodide/v0.26.2/full/python_dateutil-2.9.0.post0-py2.py3-none-any.whl");
    await pyodide.loadPackage("https://cdn.jsdelivr.net/pyodide/v0.26.2/full/six-1.16.0-py2.py3-none-any.whl");
    await pyodide.loadPackage("https://cdn.jsdelivr.net/pyodide/v0.26.2/full/pytz-2024.1-py2.py3-none-any.whl");
    await pyodide.loadPackage("https://cdn.jsdelivr.net/pyodide/v0.26.2/full/typing_extensions-4.11.0-py3-none-any.whl");
    await pyodide.loadPackage("/skl2onnx-1.17.0-py2.py3-none-any.whl");
    await pyodide.loadPackage("/imbalanced_learn-0.12.3-py3-none-any.whl");
    await pyodide.loadPackage("/onnxconverter_common-1.14.0-py2.py3-none-any.whl");
    await pyodide.loadPackage("https://cdn.jsdelivr.net/pyodide/v0.27.2/full/httpx-0.28.1-py3-none-any.whl");
    await pyodide.loadPackage("https://cdn.jsdelivr.net/pyodide/v0.27.2/full/ssl-1.0.0-py2.py3-none-any.whl");

    //////////////////////////////////////////

    const micropip = pyodide.pyimport("micropip");


    await pyodide.loadPackage("/falcon_ml-0.8.0-py3-none-any.whl");

    await pyodide.loadPackage(
        "/onnx-1.16.2-cp312-cp312-pyodide_2024_0_wasm32.whl"
    );

    await pyodide.loadPackage("/dfs_webworker-0.1.0-py3-none-any.whl");

    await pyodide.loadPackage("/promptopt-0.1.0-py3-none-any.whl")


    await micropip.install("scipy==1.14.1");
    await pyodide.loadPackage("https://files.pythonhosted.org/packages/28/09/c4d329f7969443cdd4d482048ca406b6f61cda3c8e99ace71feaec7c8734/optuna-4.2.1-py3-none-any.whl");
    await pyodide.loadPackage("https://files.pythonhosted.org/packages/e3/51/9b208e85196941db2f0654ad0357ca6388ab3ed67efdbfc799f35d1f83aa/colorlog-6.9.0-py3-none-any.whl");
    await pyodide.loadPackage("https://files.pythonhosted.org/packages/d0/30/dc54f88dd4a2b5dc8a0279bdd7270e735851848b762aeb1c1184ed1f6b14/tqdm-4.67.1-py3-none-any.whl")
    await micropip.install("sqlite3");
    await micropip.install("pyfnx-utils==0.0.1");
    await micropip.install("fnnx");
    await micropip.install("numpy");

    self.pyodide = pyodide;
    return true;
}

self.pyodideReadyPromise = initPyWorker();


async function pingPython() {
    const dfw = self.pyodide.pyimport("dfs_webworker");
    const res = await dfw.ping();
}

async function invokeRoute(route, data) {
    const dfw = self.pyodide.pyimport("dfs_webworker");
    const res = (await dfw.invoke(route, data)).toJs();
    return JSON.parse(JSON.stringify(res));
}


// LEGACY ROUTES HANDLED DIRECTLY IN THE WORKER

async function tabularTrain(task, data, target, groups) {

    // TODO: groups
    const payload = { "data": data, "target": target, "task": task };
    return await invokeRoute("/tabular/train", payload)
}

async function tabularPredict(model_id, data) {
    const payload = { "model_id": model_id, "data": data };
    return await invokeRoute("/tabular/predict", payload);
}

async function tabularDeallocate(model_id) {
    const payload = { "model_id": model_id };
    return await invokeRoute("/tabular/deallocate", payload);
}

self.onmessage = async (event) => {
    const m = event.data;
    const pyodideReady = await self.pyodideReadyPromise;
    switch (m.message) {
        case MESSAGES.LOAD_PYODIDE:
            if (pyodideReady) {
                self.postMessage({ message: m.message, id: m.id, payload: true });
            }
            // TODO: if an error occurs here, it has to be handled in the frontend
            break;
        case "tabular_train":
            const tabularResult = await tabularTrain(m.payload.task, m.payload.data, m.payload.target, m.payload.groups);
            self.postMessage({ message: m.message, id: m.id, payload: tabularResult });
            break;
        case "tabular_predict":
            const tabularPredictResult = await tabularPredict(m.payload.model_id, m.payload.data);
            self.postMessage({ message: m.message, id: m.id, payload: tabularPredictResult });
            break;
        case "tabular_deallocate":
            const tabularDeallocateResult = await tabularDeallocate(m.payload.model_id);
            self.postMessage({ message: m.message, id: m.id, payload: tabularDeallocateResult });
            break;
        case "invokeRoute":
            const result = await invokeRoute(m.payload.route, m.payload.data);
            self.postMessage({ message: m.message, id: m.id, payload: result });
            break;
        case "interrupt":
            const interrupt = new Uint8Array(new SharedArrayBuffer(1));
            interrupt[0] = 2;
            self.pyodide.setInterruptBuffer(interrupt);
            break;
    }
};
