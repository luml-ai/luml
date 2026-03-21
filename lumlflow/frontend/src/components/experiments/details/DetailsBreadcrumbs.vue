<template>
  <Breadcrumb :model="breadcrumbs" :pt="BREADCRUMBS_PT">
    <template #item="{ item, props }">
      <router-link v-if="item.route" v-slot="{ href, navigate }" :to="item.route" custom>
        <a :href="href" v-bind="props.action" @click="navigate">
          {{ item.label }}
        </a>
      </router-link>
      <a v-else :href="item.url" :target="item.target" v-bind="props.action">
        {{ item.label }}
      </a>
    </template>
  </Breadcrumb>
</template>

<script setup lang="ts">
import { ROUTE_NAMES } from '@/router/router.const'
import { computed } from 'vue'
import { Breadcrumb } from 'primevue'
import { BREADCRUMBS_PT } from './details.const'

interface Props {
  groupName: string
  groupId: string
  experimentName: string
  experimentId: string
}

const props = defineProps<Props>()

const breadcrumbs = computed(() => [
  { label: 'Groups ', route: { name: ROUTE_NAMES.HOME } },
  {
    label: props.groupName,
    route: { name: ROUTE_NAMES.EXPERIMENT, params: { groupId: props.groupId } },
  },
  {
    label: props.experimentName,
    route: {
      name: ROUTE_NAMES.EXPERIMENT_OVERVIEW,
      params: { groupId: props.groupId, experimentId: props.experimentId },
    },
  },
])
</script>

<style scoped></style>
