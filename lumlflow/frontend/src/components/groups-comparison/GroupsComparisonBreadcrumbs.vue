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

const BREADCRUMBS_PT = {
  root: {
    style: 'padding-left: 0',
  },
}

const breadcrumbs = computed(() => [
  { label: 'Experiment groups', route: { name: ROUTE_NAMES.HOME } },
])
</script>

<style scoped></style>
