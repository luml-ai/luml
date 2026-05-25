import { Model } from '@fnnx-ai/web';
import { type ClassificationMetrics, type RegressionMetrics, type TabularMetrics } from '../data-processing/interfaces';
import type { Manifest, MetaEntry } from '@fnnx-ai/common/dist/interfaces';
import type { FileIndex } from '../api/artifacts/interfaces';
export declare enum FNNX_PRODUCER_TAGS_METADATA_ENUM {
    contains_classification_metrics_v1 = "falcon.beastbyte.ai::tabular_classification_metrics:v1",
    contains_regression_metrics_v1 = "falcon.beastbyte.ai::tabular_regression_metrics:v1",
    contains_registry_metricss_v1 = "dataforce.studio::registry_metrics:v1",
    contains_prompt_fusion_v1 = "dataforce.studio/prompt-fusion::graph_fe_def:v1"
}
export declare enum FNNX_PRODUCER_TAGS_MANIFEST_ENUM {
    tabular_classification_v1 = "dataforce.studio::tabular_classification:v1",
    tabular_regression_v1 = "dataforce.studio::tabular_regression:v1",
    prompt_optimization_v1 = "dataforce.studio::prompt_optimization:v1"
}
export declare enum FNNX_VARIABLES_TAGS_ENUM {
    runtime_secret_v1 = "dataforce.studio::runtime_secret:v1"
}
export declare const SECRET_TAGS: FNNX_VARIABLES_TAGS_ENUM[];
declare class FnnxServiceClass {
    createModelFromFile(file: File): Promise<any>;
    getRegistryMetrics(model: Model): any;
    getMetadataByTag(metaArray: Array<MetaEntry>, availableTags: FNNX_PRODUCER_TAGS_METADATA_ENUM[]): any;
    getTabularMetrics(metadata: Array<MetaEntry>): any;
    getPromptOptimizationData(metadata: Array<MetaEntry>): any;
    getTypeTag(manifest: Manifest): FNNX_PRODUCER_TAGS_MANIFEST_ENUM | null;
    getTop5TabularFeatures(metrics: TabularMetrics): {
        scaled_importance: number;
        feature_name: string;
    }[];
    getTabularTotalScore(metrics: TabularMetrics): number;
    prepareTabularMetrics(metrics: ClassificationMetrics | RegressionMetrics, tag: FNNX_PRODUCER_TAGS_MANIFEST_ENUM): string[];
    getClassificationMetricsV1(metrics: ClassificationMetrics): string[];
    getRegressionMetricsV1(metrics: RegressionMetrics): string[];
    isTabularTag(tag: FNNX_PRODUCER_TAGS_MANIFEST_ENUM): boolean;
    isPromptOptimizationTag(tag: FNNX_PRODUCER_TAGS_MANIFEST_ENUM): boolean;
    findHtmlCard(fileIndex: FileIndex): string | undefined;
    getModelMetadataFileName(fileIndex: FileIndex): "meta.json" | null;
    findExperimentSnapshotArchiveName(fileIndex: FileIndex): string | undefined;
    hasAttachments(fileIndex: FileIndex): boolean;
    findAttachmentsTarPath(fileIndex: FileIndex): string | undefined;
    findAttachmentsIndexPath(fileIndex: FileIndex): string | undefined;
    getDynamicAttributes(manifest: Manifest): {
        secrets: Var[];
        notSecrets: Var[];
    };
    getEnvVars(manifest: Manifest): {
        secrets: Var[];
        notSecrets: Var[];
    };
}
export declare const FnnxService: FnnxServiceClass;
export {};
