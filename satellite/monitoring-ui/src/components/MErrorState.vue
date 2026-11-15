<template>
  <Message severity="error" class="error-state">
    <template #icon>
      <CircleAlert :size="16" />
    </template>
    <div class="error-body">
      <div class="error-text">
        <span class="error-title">{{ title }}</span>
        <span class="error-message">{{ getErrorMessage(error) }}</span>
      </div>
      <Button
        v-if="!isSessionExpired"
        label="Retry"
        severity="secondary"
        size="small"
        variant="outlined"
        @click="emit('retry')"
      >
        <template #icon>
          <RotateCcw :size="14" />
        </template>
      </Button>
    </div>
  </Message>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import Message from 'primevue/message'
import Button from 'primevue/button'
import { CircleAlert, RotateCcw } from 'lucide-vue-next'
import { SessionExpiredError } from '@/api'
import { getErrorMessage } from '@/utils/errors'

interface Props {
  error: Error
  title?: string
}

interface Emits {
  retry: []
}

const props = withDefaults(defineProps<Props>(), {
  title: 'Failed to load data',
})

const emit = defineEmits<Emits>()

const isSessionExpired = computed(() => props.error instanceof SessionExpiredError)
</script>

<style scoped>
.error-state :deep(.p-message-text) {
  flex: 1;
}

.error-body {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.error-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.error-title {
  font-size: 14px;
  font-weight: 500;
}

.error-message {
  font-size: 12px;
}
</style>
