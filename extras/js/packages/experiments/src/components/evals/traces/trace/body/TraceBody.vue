<template>
  <div class="body">
    <div class="content">
      <header class="header">
        <div class="header-left">
          <h4 class="title">
            <component :is="spanTypeData.icon" :size="16" :color="spanTypeData.color" />
            <span>{{ data.name }}</span>
          </h4>
          <div class="info">
            <History :size="12" />
            <span>{{ time }}</span>
          </div>
        </div>
        <div class="header-right">
          <AnnotationsButton
            v-if="showAnnotationsButton"
            :count="annotationsStore.spanAnnotations.length"
            @click="showAnnotations"
          />
        </div>
      </header>
      <Tabs v-model:value="currentTab" class="tabs">
        <TabList class="tabs-list" :pt="{ tabList: 'tabs-list' }">
          <Tab :value="0" class="tab">Attributes</Tab>
          <Tab :value="1" class="tab">Events</Tab>
          <Tab :value="2" class="tab">Metadata</Tab>
        </TabList>
        <TabPanels class="tabs-panels">
          <TabPanel :value="0">
            <div v-if="sortedAttributes" class="items">
              <UiMultiTypeText
                v-for="[key, value] in sortedAttributes"
                :key="key"
                :title="key"
                :text="value"
              ></UiMultiTypeText>
            </div>
            <div v-else>Attributes not found.</div>
          </TabPanel>
          <TabPanel :value="1">
            <div v-if="sortedEvents" class="items">
              <UiMultiTypeText
                v-for="[key, value] in sortedEvents"
                :key="key"
                :title="key"
                :text="value"
              >
              </UiMultiTypeText>
            </div>
            <div v-else>Events not found.</div></TabPanel
          >
          <TabPanel :value="2">
            <div v-if="data.attributes" class="items"></div>
            <div v-else>Metadata not found.</div>
          </TabPanel>
        </TabPanels>
      </Tabs>
    </div>
    <AnnotationsView
      v-if="isAnnotationsVisible"
      :artifact-id="artifactId"
      :trace-id="traceId"
      :span-id="data.span_id"
      class="annotations-view"
      @close="closeAnnotations"
    />
  </div>
</template>

<script setup lang="ts">
import type { TraceSpan } from '@experiments/interfaces/interfaces'
import { computed, ref, watch } from 'vue'
import { History } from 'lucide-vue-next'
import { Tabs, TabList, Tab, TabPanels, TabPanel, useToast } from 'primevue'
import { getErrorMessage, getFormattedTime, getSpanTypeData, safeParse } from '@experiments/helpers/helpers'
import { useAnnotationsStore } from '@experiments/store/annotations'
import { simpleErrorToast } from '@experiments/lib/primevue/data/toasts'
import UiMultiTypeText from '../../../../ui/UiMultiTypeText.vue'
import AnnotationsButton from '../../../../annotations/AnnotationsButton.vue'
import AnnotationsView from '../../../../annotations/view/AnnotationsView.vue'

type Props = {
  data: TraceSpan
  artifactId: string
  traceId: string
}

const props = defineProps<Props>()

const annotationsStore = useAnnotationsStore()
const toast = useToast()

const currentTab = ref(0)
const isAnnotationsVisible = ref(false)
const annotationsLoading = ref(false)

const spanTypeData = computed(() => {
  return getSpanTypeData(props.data.dfs_span_type)
})

const time = computed(() => {
  return getFormattedTime(props.data.start_time_unix_nano, props.data.end_time_unix_nano)
})

const sortedAttributes = computed(() => {
  if (!props.data.attributes) return null
  const parsed =
    typeof props.data.attributes === 'string'
      ? safeParse(props.data.attributes)
      : props.data.attributes
  if (!parsed || typeof parsed !== 'object') return null
  return Object.entries(parsed).sort((a, b) => {
    return a[0].localeCompare(b[0], undefined, { numeric: true, sensitivity: 'base' })
  })
})

const sortedEvents = computed(() => {
  if (!props.data.events) return null
  const parsed =
    typeof props.data.events === 'string' ? safeParse(props.data.events) : props.data.events
  if (!parsed || typeof parsed !== 'object') return null
  return Object.entries(parsed).sort((a, b) => {
    return a[0].localeCompare(b[0], undefined, { numeric: true, sensitivity: 'base' })
  })
})

const showAnnotationsButton = computed(() => {
  if (isAnnotationsVisible.value) return false
  if (annotationsStore.isEditAvailable) return true
  return annotationsStore.spanAnnotations.length > 0
})

function showAnnotations() {
  isAnnotationsVisible.value = true
}

function closeAnnotations() {
  isAnnotationsVisible.value = false
}

async function getAnnotations() {
  try {
    annotationsLoading.value = true
    await annotationsStore.getSpanAnnotations(props.artifactId, props.traceId, props.data.span_id)
  } catch (error) {
    toast.add(simpleErrorToast(getErrorMessage(error, 'Failed to get annotations')))
  } finally {
    annotationsLoading.value = false
  }
}

watch(
  () => props.data.span_id,
  async (spanId) => {
    if (!spanId) return
    await getAnnotations()
  },
  {
    immediate: true,
  },
)
</script>

<style scoped>
.body {
  flex: 1 1 auto;
  overflow-x: auto;
  display: flex;
}

.content {
  display: flex;
  flex-direction: column;
  flex: 1 1 auto;
  overflow: hidden;
  min-width: 434px;
}

.content:not(:last-child) {
  border-right: 1px solid var(--p-divider-border-color);
}

.header {
  padding: 8px 20px;
  margin-bottom: 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.title {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.info {
  padding-left: 8px;
  display: flex;
  gap: 4px;
  align-items: center;
  color: var(--p-text-muted-color);
  font-size: 12px;
  margin-bottom: 8px;
}

.tabs {
  flex: 1 1 auto;
  overflow: hidden;
}

:deep(.tabs-list) {
  border-left: none;
  border-top: none;
  border-right: none;
  background-color: transparent;
  flex: 0 0 auto;
}

.tabs-panels {
  padding: 20px;
  background-color: transparent;
  flex: 1 1 auto;
  overflow-y: auto;
}

.tab {
  border: none;
}

.items {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.annotations-view {
  max-width: 380px;
}
</style>
