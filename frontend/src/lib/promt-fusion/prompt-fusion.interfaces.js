export var ProvidersEnum;
(function (ProvidersEnum) {
    ProvidersEnum["openAi"] = "openAi";
    ProvidersEnum["ollama"] = "ollama";
})(ProvidersEnum || (ProvidersEnum = {}));
export var ProviderModelsEnum;
(function (ProviderModelsEnum) {
    ProviderModelsEnum["gpt4o"] = "gpt-4o";
    ProviderModelsEnum["gpt4o_mini"] = "gpt-4o-mini";
    ProviderModelsEnum["gpt4_1"] = "gpt-4.1";
    ProviderModelsEnum["gpt4_1_mini"] = "gpt-4.1-mini";
    ProviderModelsEnum["gpt4_1_nano"] = "gpt-4.1-nano";
    ProviderModelsEnum["gemma3_4b"] = "gemma3:4b";
    ProviderModelsEnum["llama3_1_8b"] = "llama3.1:8b";
    ProviderModelsEnum["llama3_2_3b"] = "llama3.2:3b";
    ProviderModelsEnum["llama3_3_70b"] = "llama3.3:70b";
    ProviderModelsEnum["mistral_small3_1_24b"] = "mistral-small3.1:24b";
    ProviderModelsEnum["qwen2_5_7b"] = "qwen2.5:7b";
    ProviderModelsEnum["phi4_14b"] = "phi4:14b";
    ProviderModelsEnum["phi4_mini_3_8b"] = "phi4-mini:3.8b";
})(ProviderModelsEnum || (ProviderModelsEnum = {}));
export var ModelTypeEnum;
(function (ModelTypeEnum) {
    ModelTypeEnum["teacher"] = "teacher";
    ModelTypeEnum["student"] = "student";
})(ModelTypeEnum || (ModelTypeEnum = {}));
export var ProviderStatus;
(function (ProviderStatus) {
    ProviderStatus["connected"] = "connected";
    ProviderStatus["disconnected"] = "disconnected";
})(ProviderStatus || (ProviderStatus = {}));
export var EvaluationModesEnum;
(function (EvaluationModesEnum) {
    EvaluationModesEnum["exactMatch"] = "Exact match";
    EvaluationModesEnum["llmBased"] = "LLM-as-a-judge";
    EvaluationModesEnum["none"] = "None";
})(EvaluationModesEnum || (EvaluationModesEnum = {}));
export var ProviderDynamicAttributesTagsEnum;
(function (ProviderDynamicAttributesTagsEnum) {
    ProviderDynamicAttributesTagsEnum["dataforce.studio/prompt-fusion::provider_api_key:v1"] = "apiKey";
    ProviderDynamicAttributesTagsEnum["dataforce.studio/prompt-fusion::provider_base_url:v1"] = "apiBase";
})(ProviderDynamicAttributesTagsEnum || (ProviderDynamicAttributesTagsEnum = {}));
export var ProviderAttributesMap;
(function (ProviderAttributesMap) {
    ProviderAttributesMap["apiKey"] = "api_key";
    ProviderAttributesMap["apiBase"] = "api_base";
})(ProviderAttributesMap || (ProviderAttributesMap = {}));
