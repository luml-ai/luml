import type {
  ModelSnapshot,
  ExperimentSnapshotProvider,
  SpansParams,
  EvalsInfo,
  ModelsInfo,
  ExperimentSnapshotDynamicMetrics,
  ExperimentSnapshotStaticParams,
  ModelInfo,
  BaseTraceInfo,
} from './interfaces/interfaces'
import { ExperimentSnapshotDatabaseProvider } from './providers/ExperimentSnapshotDatabaseProvider'
import { ExperimentSnapshotWorkerProxy } from './providers/ExperimentSnapshotWorkerProxy'
import type {
  ExperimentSnapshotWorkerProxyOptions,
  SnapshotSourceUrlProvider,
} from './providers/ExperimentSnapshotWorkerProxy'
import type {
  ExperimentSnapshotModelSource,
  SnapshotOpenFailure,
  SnapshotTransportStats,
} from './providers/ExperimentSnapshotDatabaseProvider'
import type {
  ExperimentSnapshotSource,
  SnapshotTransportFallback,
} from './providers/snapshot-source/openRawSnapshot'
import {
  assertSourceHeaders,
  SnapshotSourceHeaderError,
  type SnapshotSourceLocation,
  type SnapshotSourceRef,
} from './providers/snapshot-source/sourceLocation'
import {
  isSnapshotRangeUnsupported,
  isSnapshotSourceExpired,
  redactSecrets,
  SNAPSHOT_FORMAT,
  SNAPSHOT_RANGE_UNSUPPORTED,
  SNAPSHOT_SOURCE_EXPIRED,
  SNAPSHOT_SOURCE_PAGE,
  SNAPSHOT_SOURCE_REDIRECT,
  SNAPSHOT_SOURCE_TOO_LARGE,
  SNAPSHOT_TOO_LARGE_FOR_BROWSER,
  snapshotErrorFields,
  SnapshotFormatError,
  SnapshotRangeUnsupportedError,
  SnapshotSourceExpiredError,
  SnapshotSourcePageError,
  SnapshotSourceRedirectError,
  SnapshotSourceTooLargeError,
  SnapshotTooLargeForBrowserError,
} from './providers/snapshot-source/errors'
import {
  assertZipSnapshotFits,
  MAX_ZIP_ENTRY_BYTES,
} from './providers/snapshot-source/zipDirectory'
import { ExperimentSnapshotApiProvider } from './providers/ExperimentSnapshotApiProvider'
import type {
  MetricBucketsWire,
  MetricBucketsRequestWire,
  MetricCatalogWire,
} from './providers/ExperimentSnapshotApiProvider.interface'
import type {
  ExperimentMetricCatalog,
  ExperimentReadError,
  ExperimentReadErrorCode,
  ExperimentResult,
  ExperimentSnapshotStatus,
  MetricBucket,
  MetricBucketSeries,
  MetricBucketsRequest,
  MetricBucketsResponse,
  MetricCatalogEntry,
  MetricCatalogsRequest,
} from './metric-buckets/types'
import {
  INVALID_LEVEL,
  NEEDS_NEWER_READER,
  READ_FAILED,
  TIMED_OUT,
  TOO_MANY_BUCKETS,
} from './metric-buckets/types'
import {
  MetricReadTimeoutError,
  InvalidBucketLevelError,
  SnapshotNeedsNewerReaderError,
  toExperimentReadError,
  TooManyBucketsError,
} from './metric-buckets/errors'
import {
  bucketOf,
  bucketStepRange,
  chooseBucketLevel,
  MAX_BUCKET_LEVEL,
  MAX_RETURNED_BUCKETS,
} from './metric-buckets/levels'
import { IntervalSet, type Interval } from './metric-buckets/IntervalSet'
import { BucketCache, type BucketCacheOptions } from './metric-buckets/BucketCache'
import {
  planBucketRead,
  type BucketReadPlan,
  type BucketReadRequest,
  type BucketReadSource,
  type ExperimentReadPlan,
  type PlannedFetch,
  type PlannedSeries,
  type PlannerOptions,
  type ReadCost,
} from './metric-buckets/planner'
import {
  MetricBucketStore,
  metricStepRange,
  metricStepRanges,
  type ChartError,
  type ChartListener,
  type ChartSeries,
  type ChartState,
  type ChartSubscription,
  type MetricBucketSource,
  type MetricBucketStoreOptions,
  type MetricCatalogs,
  type StepInterval,
  type SubscribeOptions,
} from './metric-buckets/MetricBucketStore'
import { provideTheme } from './lib/theme/ThemeProvider'
import { useEvalsStore } from './store/evals'
import { useAnnotationsStore } from './store/annotations'
import { useDynamicMetricsStore } from './store/dynamic-metrics'
import { useTraceStore } from './store/trace'
import ExperimentSnapshot from './ExperimentSnapshot.vue'
import ComparisonHeader from './components/comparison/ComparisonHeader.vue'
import ComparisonModelsList from './components/comparison/ComparisonModelsList.vue'
import EvalsDatasetsList from './components/evals/EvalsDatasetsList.vue'
import DynamicMetrics from './components/dynamic-metrics/DynamicMetrics.vue'
import TracesDialog from './components/evals/traces/TracesDialog.vue'
import TraceDialog from './components/evals/traces/trace/TraceDialog.vue'
import TracesWrapper from './components/traces/TracesWrapper.vue'
import ExperimentStatusNotices from './components/experiment-status/ExperimentStatusNotices.vue'

export type {
  ExperimentSnapshotProvider,
  ModelSnapshot,
  SpansParams,
  EvalsInfo,
  ModelsInfo,
  ExperimentSnapshotDynamicMetrics,
  ExperimentSnapshotStaticParams,
  ModelInfo,
  BaseTraceInfo,
  ExperimentSnapshotWorkerProxyOptions,
  SnapshotSourceUrlProvider,
  ExperimentSnapshotModelSource,
  ExperimentSnapshotSource,
  SnapshotSourceLocation,
  SnapshotSourceRef,
  SnapshotTransportFallback,
  SnapshotTransportStats,
  SnapshotOpenFailure,
  StepInterval,
  SubscribeOptions,
  MetricBucketsWire,
  MetricBucketsRequestWire,
  MetricCatalogWire,
  ExperimentMetricCatalog,
  ExperimentReadError,
  ExperimentReadErrorCode,
  ExperimentResult,
  ExperimentSnapshotStatus,
  MetricBucket,
  MetricBucketSeries,
  MetricBucketsRequest,
  MetricBucketsResponse,
  MetricCatalogEntry,
  MetricCatalogsRequest,
  Interval,
  BucketCacheOptions,
  BucketReadPlan,
  BucketReadRequest,
  BucketReadSource,
  ExperimentReadPlan,
  PlannedFetch,
  PlannedSeries,
  PlannerOptions,
  ReadCost,
  ChartError,
  ChartListener,
  ChartSeries,
  ChartState,
  ChartSubscription,
  MetricBucketSource,
  MetricBucketStoreOptions,
  MetricCatalogs,
}

export {
  ExperimentSnapshot,
  ComparisonHeader,
  ComparisonModelsList,
  ExperimentSnapshotDatabaseProvider,
  ExperimentSnapshotWorkerProxy,
  DynamicMetrics,
  EvalsDatasetsList,
  provideTheme,
  TracesDialog,
  TraceDialog,
  useEvalsStore,
  ExperimentSnapshotApiProvider,
  useAnnotationsStore,
  TracesWrapper,
  ExperimentStatusNotices,
  useDynamicMetricsStore,
  useTraceStore,
  isSnapshotRangeUnsupported,
  isSnapshotSourceExpired,
  SNAPSHOT_RANGE_UNSUPPORTED,
  SNAPSHOT_SOURCE_EXPIRED,
  SNAPSHOT_SOURCE_REDIRECT,
  SNAPSHOT_SOURCE_TOO_LARGE,
  SNAPSHOT_TOO_LARGE_FOR_BROWSER,
  SNAPSHOT_SOURCE_PAGE,
  SNAPSHOT_FORMAT,
  snapshotErrorFields,
  redactSecrets,
  SnapshotFormatError,
  SnapshotRangeUnsupportedError,
  SnapshotSourceExpiredError,
  SnapshotSourcePageError,
  SnapshotSourceRedirectError,
  SnapshotSourceTooLargeError,
  SnapshotTooLargeForBrowserError,
  assertZipSnapshotFits,
  MAX_ZIP_ENTRY_BYTES,
  assertSourceHeaders,
  SnapshotSourceHeaderError,
  INVALID_LEVEL,
  NEEDS_NEWER_READER,
  READ_FAILED,
  TIMED_OUT,
  TOO_MANY_BUCKETS,
  MetricReadTimeoutError,
  InvalidBucketLevelError,
  SnapshotNeedsNewerReaderError,
  toExperimentReadError,
  TooManyBucketsError,
  bucketOf,
  bucketStepRange,
  chooseBucketLevel,
  MAX_BUCKET_LEVEL,
  MAX_RETURNED_BUCKETS,
  IntervalSet,
  BucketCache,
  planBucketRead,
  MetricBucketStore,
  metricStepRange,
  metricStepRanges,
}
