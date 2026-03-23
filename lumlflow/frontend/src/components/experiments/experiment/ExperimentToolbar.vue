<template>
  <div class="pb-5 flex justify-between items-center">
    <div class="flex items-center gap-8">
      <div class="tabular-nums">{{ experimentsStore.selectedExperiments.length }} Selected</div>
      <ExperimentButtons />
    </div>
    <div class="flex gap-2 grow justify-end">
      <TableEditColumns
        :columns="experimentsStore.tableColumns"
        :selected-columns="experimentsStore.visibleColumns"
        @edit="(data) => experimentsStore.setVisibleColumns(data)"
      />
      <div class="max-w-sm w-full">
        <IconField>
          <InputIcon
            class="left-icon"
            v-tooltip.left="{
              value: searchInputData.tooltipText,
              pt: SEARCH_ICON_TOOLTIP_PT,
            }"
          >
            <Info :size="12" :color="searchInputData.iconColor" />
          </InputIcon>
          <AutoComplete
            v-model="search"
            :suggestions="suggestions"
            placeholder="metrics.rmse < 1"
            size="small"
            fluid
            complete-on-focus
            option-group-label="label"
            option-group-children="items"
            :show-empty-message="false"
            :pt="AUTOCOMPLETE_PT"
            :virtual-scroller-options="AUTOCOMPLETE_VIRTUAL_SCROLLER_OPTIONS"
            :invalid="searchInputData.invalid"
            @complete="onComplete"
          />
          <InputIcon class="right-icon">
            <Search :size="12" :color="searchInputData.iconColor" />
          </InputIcon>
        </IconField>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  IconField,
  InputIcon,
  AutoComplete,
  type AutoCompleteCompleteEvent,
  useToast,
} from 'primevue'
import { Search, Info } from 'lucide-vue-next'
import { useExperimentsStore } from '@/store/experiments'
import {
  AUTOCOMPLETE_PT,
  AUTOCOMPLETE_TOOLTIP,
  AUTOCOMPLETE_VIRTUAL_SCROLLER_OPTIONS,
  SEARCH_ICON_TOOLTIP_PT,
} from './experiment.const'
import { apiService } from '@/api/api.service'
import { errorToast } from '@/toasts'
import { useDebounceFn } from '@vueuse/core'
import ExperimentButtons from './ExperimentButtons.vue'
import TableEditColumns from '@/components/table/TableEditColumns.vue'

const experimentsStore = useExperimentsStore()
const toast = useToast()

const search = ref(experimentsStore.queryParams.search || '')

const suggestions = ref<{ label: string; items: string[] }[]>([])

const error = ref<string | null>(null)

const dynamicMetrics = computed(() =>
  experimentsStore.dynamicMetrics.map((metric) => 'metrics.' + metric),
)

const searchInputData = computed(() => {
  if (error.value) {
    return {
      tooltipText: error.value,
      iconColor: 'var(--p-message-error-color)',
      invalid: true,
    }
  } else {
    return {
      tooltipText: AUTOCOMPLETE_TOOLTIP,
      iconColor: 'var(--p-iconfield-icon-color)',
      invalid: false,
    }
  }
})

const staticParams = computed(() => experimentsStore.staticParams.map((param) => 'params.' + param))

async function onSearch() {
  try {
    const valid = await validateSearch(search.value)
    if (!valid) {
      return
    }
    experimentsStore.setQueryParams({ ...experimentsStore.queryParams, search: search.value })
  } catch (e) {
    toast.add(errorToast(e, 'Invalid search query'))
  }
}

function onComplete(event: AutoCompleteCompleteEvent) {
  const filteredMetrics = dynamicMetrics.value.filter((metric) => metric.includes(event.query))
  const filteredStaticParams = staticParams.value.filter((param) => param.includes(event.query))
  const list = []
  if (filteredMetrics.length > 0) {
    list.push({
      label: 'Metrics',
      items: filteredMetrics,
    })
  }
  if (filteredStaticParams.length > 0) {
    list.push({
      label: 'Parameters',
      items: filteredStaticParams,
    })
  }
  suggestions.value = list
}

async function validateSearch(query: string) {
  const response = await apiService.validateExperimentSearch(query)
  if (!response.valid) {
    error.value = response.error
  } else {
    error.value = null
  }
  return response.valid
}

const debouncedOnSearch = useDebounceFn(onSearch, 500)

watch(search, debouncedOnSearch)
</script>

<style scoped>
:deep(.p-autocomplete-input) {
  padding-inline-start: 30px !important;
  padding-inline-end: 30px !important;
}

.left-icon {
  inset-inline-start: 9px !important;
}

.right-icon {
  inset-inline-end: 9px !important;
}
</style>
