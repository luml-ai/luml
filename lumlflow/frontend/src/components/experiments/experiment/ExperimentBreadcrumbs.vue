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
import type { Group } from '@/store/groups/groups.interface'
import { ROUTE_NAMES } from '@/router/router.const'
import { computed } from 'vue'
import { Breadcrumb } from 'primevue'
import { BREADCRUMBS_PT } from './experiment.const'

interface Props {
  experiment: Group
}

const props = defineProps<Props>()

const breadcrumbs = computed(() => [
  { label: 'Experiments group ', route: { name: ROUTE_NAMES.HOME } },
  {
    label: props.experiment.name,
    route: { name: ROUTE_NAMES.EXPERIMENT, params: { experimentId: props.experiment.id } },
  },
])
</script>

<style scoped></style>
