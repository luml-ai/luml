<template>
  <div class="card">
    <div class="header">
      <img class="image" alt="" :src="task.icon" width="48" height="48" />
      <div v-tooltip.left="task.tooltipData" autoHide="false">
        <circle-help :size="20" class="tooltip-icon" />
      </div>
    </div>
    <div class="content">
      <div class="card-title">
        {{ task.title }}
      </div>
      <div class="text">
        <p>
          {{ task.description }}
        </p>
      </div>
    </div>
    <div class="footer" v-if="task.btnText">
      <SplitButton
        v-if="task.dropdownOptions?.length"
        :label="task.btnText"
        :model="dropdownItems"
        severity="secondary"
        class="w-full"
        @click="onButtonClick"
      />
      <d-button
        v-else
        :label="task.btnText"
        severity="secondary"
        class="w-full"
        :disabled="task.isDisabled"
        @click="onButtonClick"
      />
    </div>
    <task-modal v-if="isPromptFusionTask" v-model="isPopupVisible" />
  </div>
</template>

<script setup lang="ts">
import type { TaskData } from './interfaces'
import { CircleHelp } from 'lucide-vue-next'
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import SplitButton from 'primevue/splitbutton'
import TaskModal from '@/components/express-tasks/prompt-fusion/TaskModal.vue'
import { AnalyticsService, AnalyticsTrackKeysEnum } from '@/lib/analytics/AnalyticsService'

type TProps = {
  task: TaskData
}

const props = defineProps<TProps>()

const router = useRouter()

const isPopupVisible = ref(false)
const isPromptFusionTask = computed(() => props.task.id === 5)

function onButtonClick() {
  AnalyticsService.track(AnalyticsTrackKeysEnum.select_task, { task: props.task.analyticsTaskName })
  if (props.task.linkName) router.push({ name: props.task.linkName })
  else if (isPromptFusionTask.value) {
    isPopupVisible.value = true
  }
}

const dropdownItems = computed(() =>
  (props.task.dropdownOptions || []).map((opt) => ({
    label: opt.label,
    command: () => {
      AnalyticsService.track(AnalyticsTrackKeysEnum.select_task, {
        task: props.task.analyticsTaskName,
      })
      const target = opt.route || props.task.linkName
      if (target) router.push({ name: target })
      else if (isPromptFusionTask.value) isPopupVisible.value = true
    },
  })),
)
</script>

<style scoped>
.card {
  padding: 24px;
  border-radius: 8px;
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  box-shadow: var(--card-shadow);
  display: flex;
  flex-direction: column;
}
.header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 16px;
  color: var(--p-icon-muted-color);
}
.image {
  width: 48px;
  height: 48px;
}
.content {
  display: flex;
  flex-direction: column;
  flex: 1 1 auto;
}
.content:not(:last-child) {
  margin-bottom: 24px;
}
.card-title {
  font-size: 20px;
  font-weight: 500;
  line-height: 1.2;
  margin-bottom: 8px;
}
.text {
  color: var(--p-text-muted-color);
  font-size: 14px;
  line-height: 1.42;
}
:deep(.p-splitbutton) {
  width: 100%;
}
:deep(.p-splitbutton .p-splitbutton-button) {
  flex: 1;
}
:deep(.p-splitbutton .p-splitbutton-dropdown) {
  border-left: 1.5px solid var(--p-card-background);
}
:deep(.p-splitbutton .p-splitbutton-dropdown .p-icon) {
  width: 10px;
  height: 10px;
}
@media (max-width: 768px) {
  .tooltip-icon {
    display: none;
  }
  .card {
    padding: 15px;
  }
}
</style>
