import { Model } from '@fnnx/web'
import {
  type ClassificationMetrics,
  type RegressionMetrics,
  type TabularMetrics,
} from '../data-processing/interfaces'
import type { Manifest, MetaEntry, Var } from '@fnnx/common/dist/interfaces'
import { fixNumber, getFormattedMetric, toPercent } from '@/helpers/helpers'
import type { FileIndex } from '../api/orbit-ml-models/interfaces'

export enum FNNX_PRODUCER_TAGS_METADATA_ENUM {
  contains_classification_metrics_v1 = 'falcon.beastbyte.ai::tabular_classification_metrics:v1',
  contains_regression_metrics_v1 = 'falcon.beastbyte.ai::tabular_regression_metrics:v1',
  contains_registry_metricss_v1 = 'dataforce.studio::registry_metrics:v1',
  contains_prompt_fusion_v1 = 'dataforce.studio/prompt-fusion::graph_fe_def:v1',
}

export enum FNNX_PRODUCER_TAGS_MANIFEST_ENUM {
  tabular_classification_v1 = 'dataforce.studio::tabular_classification:v1',
  tabular_regression_v1 = 'dataforce.studio::tabular_regression:v1',
  prompt_optimization_v1 = 'dataforce.studio::prompt_optimization:v1',
}

export enum FNNX_VARIABLES_TAGS_ENUM {
  runtime_secret_v1 = 'dataforce.studio::runtime_secret:v1',
}

export const SECRET_TAGS = [FNNX_VARIABLES_TAGS_ENUM.runtime_secret_v1]

class FnnxServiceClass {
  async createModelFromFile(file: File) {
    const allowedExtensions = ['.fnnx', '.pyfnx', '.dfs', '.luml']
    if (!allowedExtensions.some((ext) => file.name.endsWith(ext))) {
      throw new Error('Incorrect file format')
    }
    const buffer = await file.arrayBuffer()
    return Model.fromBuffer(buffer)
  }

  getRegistryMetrics(model: Model) {
    // extract the metrics to be used in the registry
    const tag = this.getTypeTag(model.getManifest())
    if (tag) {
      switch (tag) {
        case FNNX_PRODUCER_TAGS_MANIFEST_ENUM.tabular_classification_v1:
        case FNNX_PRODUCER_TAGS_MANIFEST_ENUM.tabular_regression_v1:
          const tabularMetrics = this.getTabularMetrics(model.getMetadata())
          const tabularEvalMetrics =
            tabularMetrics.performance.eval_holdout || tabularMetrics.performance.eval_cv || {}
          return Object.fromEntries(
            Object.entries(tabularEvalMetrics).filter(([key, value]) => key !== 'N_SAMPLES'),
          )
      }
    }
    const customMetrics = this.getMetadataByTag(model.getMetadata(), [
      FNNX_PRODUCER_TAGS_METADATA_ENUM.contains_registry_metricss_v1,
    ])
    if (customMetrics) {
      return customMetrics.metrics || {}
    }
    return {}
  }

  getMetadataByTag(metaArray: Array<MetaEntry>, availableTags: FNNX_PRODUCER_TAGS_METADATA_ENUM[]) {
    // extracts the first available metadata entry that a metadata tag
    for (const meta of metaArray) {
      const tag = meta.producer_tags.find((tag) =>
        availableTags.includes(tag as FNNX_PRODUCER_TAGS_METADATA_ENUM),
      )
      if (tag) return meta.payload
    }
    return null
  }

  getTabularMetrics(metadata: Array<MetaEntry>) {
    const availableTags = [
      FNNX_PRODUCER_TAGS_METADATA_ENUM.contains_classification_metrics_v1,
      FNNX_PRODUCER_TAGS_METADATA_ENUM.contains_regression_metrics_v1,
    ]
    return this.getMetadataByTag(metadata, availableTags)?.metrics || null
  }

  getPromptOptimizationData(metadata: Array<MetaEntry>): any {
    const availableTags = [FNNX_PRODUCER_TAGS_METADATA_ENUM.contains_prompt_fusion_v1]
    return this.getMetadataByTag(metadata, availableTags)
  }

  getTypeTag(manifest: Manifest) {
    // extracts the extract tag that is used to determine the type of the model
    const availableTags = Object.values(FNNX_PRODUCER_TAGS_MANIFEST_ENUM)
    const tag = (manifest.producer_tags as FNNX_PRODUCER_TAGS_MANIFEST_ENUM[]).find((tag) =>
      availableTags.includes(tag as FNNX_PRODUCER_TAGS_MANIFEST_ENUM),
    )
    return tag || null
  }

  getTop5TabularFeatures(metrics: TabularMetrics) {
    return (
      metrics.permutation_feature_importance_train.importances
        .filter((item, index) => index < 5)
        .map((feature) => ({
          ...feature,
          scaled_importance: Math.round(feature.scaled_importance * 100),
        })) || []
    )
  }

  getTabularTotalScore(metrics: TabularMetrics) {
    if (metrics.performance.eval_cv) {
      return toPercent(metrics.performance.eval_cv.SC_SCORE)
    } else if (metrics.performance.eval_holdout) {
      return toPercent(metrics.performance.eval_holdout.SC_SCORE)
    } else {
      return 0
    }
  }

  prepareTabularMetrics(
    metrics: ClassificationMetrics | RegressionMetrics,
    tag: FNNX_PRODUCER_TAGS_MANIFEST_ENUM,
  ) {
    if (tag === FNNX_PRODUCER_TAGS_MANIFEST_ENUM.tabular_classification_v1) {
      return this.getClassificationMetricsV1(metrics as ClassificationMetrics)
    } else if (tag === FNNX_PRODUCER_TAGS_MANIFEST_ENUM.tabular_regression_v1) {
      return this.getRegressionMetricsV1(metrics as RegressionMetrics)
    } else {
      return []
    }
  }

  getClassificationMetricsV1(metrics: ClassificationMetrics) {
    return [
      fixNumber(metrics.ACC, 2),
      fixNumber(metrics.PRECISION, 2),
      fixNumber(metrics.RECALL, 2),
      fixNumber(metrics.F1, 2),
    ]
  }

  getRegressionMetricsV1(metrics: RegressionMetrics) {
    return [
      getFormattedMetric(metrics.MSE),
      getFormattedMetric(metrics.RMSE),
      getFormattedMetric(metrics.MAE),
      getFormattedMetric(metrics.R2),
    ]
  }

  isTabularTag(tag: FNNX_PRODUCER_TAGS_MANIFEST_ENUM) {
    return [
      FNNX_PRODUCER_TAGS_MANIFEST_ENUM.tabular_classification_v1,
      FNNX_PRODUCER_TAGS_MANIFEST_ENUM.tabular_regression_v1,
    ].includes(tag)
  }

  isPromptOptimizationTag(tag: FNNX_PRODUCER_TAGS_MANIFEST_ENUM) {
    return [FNNX_PRODUCER_TAGS_MANIFEST_ENUM.prompt_optimization_v1].includes(tag)
  }

  findHtmlCard(fileIndex: FileIndex) {
    const regex = /meta_artifacts\/dataforce\.studio~c~~c~[^/]+~c~v1~~et~~.+?\/model_card\.zip$/
    return Object.keys(fileIndex).find((file) => regex.test(file))
  }

  getModelMetadataFileName(fileIndex: FileIndex) {
    if (fileIndex['meta.json']) return 'meta.json'
    return null
  }

  findExperimentSnapshotArchiveName(fileIndex: FileIndex) {
    const regex =
      /meta_artifacts\/dataforce\.studio~c~~c~experiment_snapshot~c~v1~~et~~[^/]+\/exp\.db\.zip$/
    return Object.keys(fileIndex).find((file) => regex.test(file))
  }

  getDynamicAttributes(manifest: Manifest) {
    const secrets: Var[] = []
    const notSecrets: Var[] = []
    manifest.dynamic_attributes.forEach((attribute) => {
      const isSecret = attribute.tags?.find((tag) =>
        SECRET_TAGS.includes(tag as FNNX_VARIABLES_TAGS_ENUM),
      )
      if (isSecret) {
        secrets.push(attribute)
      } else {
        notSecrets.push(attribute)
      }
    })
    return { secrets, notSecrets }
  }

  getEnvVars(manifest: Manifest) {
    const secrets: Var[] = []
    const notSecrets: Var[] = []
    manifest.env_vars.forEach((attribute) => {
      const isSecret = attribute.tags?.find((tag) =>
        SECRET_TAGS.includes(tag as FNNX_VARIABLES_TAGS_ENUM),
      )
      if (isSecret) {
        secrets.push(attribute)
      } else {
        notSecrets.push(attribute)
      }
    })
    return { secrets, notSecrets }
  }
}

export const FnnxService = new FnnxServiceClass()
