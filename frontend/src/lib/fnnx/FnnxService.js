import { Model } from '@fnnx-ai/web';
import { fixNumber, getFormattedMetric, toPercent } from '@/helpers/helpers';
export var FNNX_PRODUCER_TAGS_METADATA_ENUM;
(function (FNNX_PRODUCER_TAGS_METADATA_ENUM) {
    FNNX_PRODUCER_TAGS_METADATA_ENUM["contains_classification_metrics_v1"] = "falcon.beastbyte.ai::tabular_classification_metrics:v1";
    FNNX_PRODUCER_TAGS_METADATA_ENUM["contains_regression_metrics_v1"] = "falcon.beastbyte.ai::tabular_regression_metrics:v1";
    FNNX_PRODUCER_TAGS_METADATA_ENUM["contains_registry_metricss_v1"] = "dataforce.studio::registry_metrics:v1";
    FNNX_PRODUCER_TAGS_METADATA_ENUM["contains_prompt_fusion_v1"] = "dataforce.studio/prompt-fusion::graph_fe_def:v1";
})(FNNX_PRODUCER_TAGS_METADATA_ENUM || (FNNX_PRODUCER_TAGS_METADATA_ENUM = {}));
export var FNNX_PRODUCER_TAGS_MANIFEST_ENUM;
(function (FNNX_PRODUCER_TAGS_MANIFEST_ENUM) {
    FNNX_PRODUCER_TAGS_MANIFEST_ENUM["tabular_classification_v1"] = "dataforce.studio::tabular_classification:v1";
    FNNX_PRODUCER_TAGS_MANIFEST_ENUM["tabular_regression_v1"] = "dataforce.studio::tabular_regression:v1";
    FNNX_PRODUCER_TAGS_MANIFEST_ENUM["prompt_optimization_v1"] = "dataforce.studio::prompt_optimization:v1";
})(FNNX_PRODUCER_TAGS_MANIFEST_ENUM || (FNNX_PRODUCER_TAGS_MANIFEST_ENUM = {}));
export var FNNX_VARIABLES_TAGS_ENUM;
(function (FNNX_VARIABLES_TAGS_ENUM) {
    FNNX_VARIABLES_TAGS_ENUM["runtime_secret_v1"] = "dataforce.studio::runtime_secret:v1";
})(FNNX_VARIABLES_TAGS_ENUM || (FNNX_VARIABLES_TAGS_ENUM = {}));
export const SECRET_TAGS = [FNNX_VARIABLES_TAGS_ENUM.runtime_secret_v1];
class FnnxServiceClass {
    async createModelFromFile(file) {
        const allowedExtensions = ['.fnnx', '.pyfnx', '.dfs', '.luml'];
        if (!allowedExtensions.some((ext) => file.name.endsWith(ext))) {
            throw new Error('Incorrect file format');
        }
        const buffer = await file.arrayBuffer();
        return Model.fromBuffer(buffer);
    }
    getRegistryMetrics(model) {
        // extract the metrics to be used in the registry
        const tag = this.getTypeTag(model.getManifest());
        if (tag) {
            switch (tag) {
                case FNNX_PRODUCER_TAGS_MANIFEST_ENUM.tabular_classification_v1:
                case FNNX_PRODUCER_TAGS_MANIFEST_ENUM.tabular_regression_v1:
                    const tabularMetrics = this.getTabularMetrics(model.getMetadata());
                    const tabularEvalMetrics = tabularMetrics.performance.eval_holdout || tabularMetrics.performance.eval_cv || {};
                    return Object.fromEntries(Object.entries(tabularEvalMetrics).filter(([key, value]) => key !== 'N_SAMPLES'));
            }
        }
        const customMetrics = this.getMetadataByTag(model.getMetadata(), [
            FNNX_PRODUCER_TAGS_METADATA_ENUM.contains_registry_metricss_v1,
        ]);
        if (customMetrics) {
            return customMetrics.metrics || {};
        }
        return {};
    }
    getMetadataByTag(metaArray, availableTags) {
        // extracts the first available metadata entry that a metadata tag
        for (const meta of metaArray) {
            const tag = meta.producer_tags?.find((tag) => availableTags.includes(tag));
            if (tag)
                return meta.payload;
        }
        return null;
    }
    getTabularMetrics(metadata) {
        const availableTags = [
            FNNX_PRODUCER_TAGS_METADATA_ENUM.contains_classification_metrics_v1,
            FNNX_PRODUCER_TAGS_METADATA_ENUM.contains_regression_metrics_v1,
        ];
        return this.getMetadataByTag(metadata, availableTags)?.metrics || null;
    }
    getPromptOptimizationData(metadata) {
        const availableTags = [FNNX_PRODUCER_TAGS_METADATA_ENUM.contains_prompt_fusion_v1];
        return this.getMetadataByTag(metadata, availableTags);
    }
    getTypeTag(manifest) {
        // extracts the extract tag that is used to determine the type of the model
        const availableTags = Object.values(FNNX_PRODUCER_TAGS_MANIFEST_ENUM);
        const tag = manifest.producer_tags.find((tag) => availableTags.includes(tag));
        return tag || null;
    }
    getTop5TabularFeatures(metrics) {
        return (metrics.permutation_feature_importance_train.importances
            .filter((item, index) => index < 5)
            .map((feature) => ({
            ...feature,
            scaled_importance: Math.round(feature.scaled_importance * 100),
        })) || []);
    }
    getTabularTotalScore(metrics) {
        if (metrics.performance.eval_cv) {
            return toPercent(metrics.performance.eval_cv.SC_SCORE);
        }
        else if (metrics.performance.eval_holdout) {
            return toPercent(metrics.performance.eval_holdout.SC_SCORE);
        }
        else {
            return 0;
        }
    }
    prepareTabularMetrics(metrics, tag) {
        if (tag === FNNX_PRODUCER_TAGS_MANIFEST_ENUM.tabular_classification_v1) {
            return this.getClassificationMetricsV1(metrics);
        }
        else if (tag === FNNX_PRODUCER_TAGS_MANIFEST_ENUM.tabular_regression_v1) {
            return this.getRegressionMetricsV1(metrics);
        }
        else {
            return [];
        }
    }
    getClassificationMetricsV1(metrics) {
        return [
            fixNumber(metrics.ACC, 2),
            fixNumber(metrics.PRECISION, 2),
            fixNumber(metrics.RECALL, 2),
            fixNumber(metrics.F1, 2),
        ];
    }
    getRegressionMetricsV1(metrics) {
        return [
            getFormattedMetric(metrics.MSE),
            getFormattedMetric(metrics.RMSE),
            getFormattedMetric(metrics.MAE),
            getFormattedMetric(metrics.R2),
        ];
    }
    isTabularTag(tag) {
        return [
            FNNX_PRODUCER_TAGS_MANIFEST_ENUM.tabular_classification_v1,
            FNNX_PRODUCER_TAGS_MANIFEST_ENUM.tabular_regression_v1,
        ].includes(tag);
    }
    isPromptOptimizationTag(tag) {
        return [FNNX_PRODUCER_TAGS_MANIFEST_ENUM.prompt_optimization_v1].includes(tag);
    }
    findHtmlCard(fileIndex) {
        const regex = /meta_artifacts\/dataforce\.studio~c~~c~[^/]+~c~v1~~et~~.+?\/(?:model_card|dataset_card)\.zip$|^card\.zip$/;
        return Object.keys(fileIndex).find((file) => regex.test(file));
    }
    getModelMetadataFileName(fileIndex) {
        if (fileIndex['meta.json'])
            return 'meta.json';
        return null;
    }
    findExperimentSnapshotArchiveName(fileIndex) {
        const regex = /meta_artifacts\/dataforce\.studio~c~~c~experiment_snapshot~c~v1~~et~~[^/]+\/exp\.db\.zip$|^exp\.db\.zip$/;
        return Object.keys(fileIndex).find((file) => regex.test(file));
    }
    hasAttachments(fileIndex) {
        return !!this.findAttachmentsTarPath(fileIndex);
    }
    findAttachmentsTarPath(fileIndex) {
        const regex = /meta_artifacts\/dataforce\.studio~c~~c~experiment_snapshot~c~v1~~et~~[^/]+\/attachments\.tar$|^attachments\.tar$/;
        return Object.keys(fileIndex).find((path) => regex.test(path));
    }
    findAttachmentsIndexPath(fileIndex) {
        const regex = /meta_artifacts\/dataforce\.studio~c~~c~experiment_snapshot~c~v1~~et~~[^/]+\/attachments\.index\.json$|^attachments\.index\.json$/;
        return Object.keys(fileIndex).find((path) => regex.test(path));
    }
    getDynamicAttributes(manifest) {
        const secrets = [];
        const notSecrets = [];
        manifest.dynamic_attributes.forEach((attribute) => {
            const isSecret = attribute.tags?.find((tag) => SECRET_TAGS.includes(tag));
            if (isSecret) {
                secrets.push(attribute);
            }
            else {
                notSecrets.push(attribute);
            }
        });
        return { secrets, notSecrets };
    }
    getEnvVars(manifest) {
        const secrets = [];
        const notSecrets = [];
        manifest.env_vars.forEach((attribute) => {
            const isSecret = attribute.tags?.find((tag) => SECRET_TAGS.includes(tag));
            if (isSecret) {
                secrets.push(attribute);
            }
            else {
                notSecrets.push(attribute);
            }
        });
        return { secrets, notSecrets };
    }
}
export const FnnxService = new FnnxServiceClass();
