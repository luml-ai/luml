<template>
  <div class="h-full flex gap-6 min-h-0">
    <aside class="w-56 shrink-0 overflow-y-auto pr-2">
      <div v-for="group in sectionGroups" :key="group" class="mb-5">
        <p class="text-sm text-muted-color mb-1.5">{{ group }}</p>
        <nav class="flex flex-col">
          <RouterLink
            v-for="section in sectionsIn(group)"
            :key="section.id"
            :to="`/flow/design/${section.id}`"
            class="px-2.5 py-1.5 rounded-lg text-base"
            :class="
              section.id === active.id
                ? 'bg-primary-50 text-primary-700 dark:bg-primary-500/15 dark:text-primary-300 font-medium'
                : 'text-muted-color hover:bg-surface-100 dark:hover:bg-surface-800'
            "
          >
            {{ section.label }}
          </RouterLink>
        </nav>
      </div>
    </aside>

    <main class="flex-1 min-w-0 overflow-y-auto pb-12">
      <header class="mb-10">
        <h3 class="text-2xl font-medium">{{ active.label }}</h3>
      </header>
      <component :is="active.component" />
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { sectionById, sectionGroups, sections, type GallerySection } from './sections'

const route = useRoute()

const active = computed(() => sectionById(route.params.section as string | undefined))

function sectionsIn(group: GallerySection['group']): GallerySection[] {
  return sections.filter((section) => section.group === group)
}
</script>
