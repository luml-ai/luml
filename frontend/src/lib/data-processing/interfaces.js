export var WebworkerMessage;
(function (WebworkerMessage) {
    WebworkerMessage["LOAD_PYODIDE"] = "LOAD_PYODIDE";
    // TABULAR_PREDICT = 'tabular_predict',
    // TABULAR_TRAIN = 'tabular_train',
    // TABULAR_DEALLOCATE = 'tabular_deallocate',
    WebworkerMessage["INVOKE_ROUTE"] = "invokeRoute";
    WebworkerMessage["INTERRUPT"] = "interrupt";
})(WebworkerMessage || (WebworkerMessage = {}));
export var WEBWORKER_ROUTES_ENUM;
(function (WEBWORKER_ROUTES_ENUM) {
    WEBWORKER_ROUTES_ENUM["TABULAR_TRAIN"] = "/tabular/train";
    WEBWORKER_ROUTES_ENUM["TABULAR_PREDICT"] = "/tabular/predict";
    WEBWORKER_ROUTES_ENUM["TABULAR_DEALLOCATE"] = "/tabular/deallocate";
    WEBWORKER_ROUTES_ENUM["PROMPT_OPTIMIZATION_TRAIN"] = "/prompt_optimization/train";
    WEBWORKER_ROUTES_ENUM["PROMPT_OPTIMIZATION_PREDICT"] = "/prompt_optimization/predict";
    WEBWORKER_ROUTES_ENUM["STORE_DEALLOCATE"] = "/store/deallocate";
    WEBWORKER_ROUTES_ENUM["PYFUNC_INIT"] = "/pyfunc/init";
    WEBWORKER_ROUTES_ENUM["PYFUNC_COMPUTE"] = "/pyfunc/compute";
    WEBWORKER_ROUTES_ENUM["PYFUNC_DEINIT"] = "/pyfunc/deinit";
})(WEBWORKER_ROUTES_ENUM || (WEBWORKER_ROUTES_ENUM = {}));
export var Tasks;
(function (Tasks) {
    Tasks["TABULAR_CLASSIFICATION"] = "tabular_classification";
    Tasks["TABULAR_REGRESSION"] = "tabular_regression";
})(Tasks || (Tasks = {}));
