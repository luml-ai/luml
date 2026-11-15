import { TabKey, type TabItem } from '@/types/tabs'

export const ML_TABS: TabItem[] = [
  { key: TabKey.OVERVIEW, label: 'Overview' },
  { key: TabKey.RUNTIME, label: 'Runtime' },
  { key: TabKey.TRACES, label: 'Traces' },
  { key: TabKey.DATA_QUALITY, label: 'Data quality' },
  { key: TabKey.FEATURE_DRIFT, label: 'Feature drift' },
  { key: TabKey.OUTPUT_DRIFT, label: 'Output drift' },
  { key: TabKey.REFERENCE_PROFILE, label: 'Reference profile' },
  { key: TabKey.ALERTS, label: 'Alerts' },
]

export const LLM_TAB_KEYS: TabKey[] = [
  TabKey.OVERVIEW,
  TabKey.RUNTIME,
  TabKey.TRACES,
  TabKey.ALERTS,
]

export const LLM_TABS: TabItem[] = ML_TABS.filter((tab) => LLM_TAB_KEYS.includes(tab.key))
