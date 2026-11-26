<template>
  <Tabs :value="view" @update:value="onChange">
    <TabList>
      <Tab v-for="item in REFERENCE_PROFILE_VIEWS" :key="item.value" :value="item.value">
        {{ item.label }}
      </Tab>
    </TabList>
  </Tabs>
</template>

<script setup lang="ts">
import Tabs from 'primevue/tabs'
import TabList from 'primevue/tablist'
import Tab from 'primevue/tab'
import { REFERENCE_PROFILE_VIEWS } from '@/constants/reference-profile'
import type { ReferenceProfileView } from '@/types/reference-profile'

const view = defineModel<ReferenceProfileView>({ required: true })

function onChange(value: string | number) {
  view.value = value as ReferenceProfileView
}
</script>
