import type { RouteLocationNormalized } from 'vue-router'

import { AppLayoutsEnum, AppLayoutToFileMap } from '@/templates/templates.types'

export async function loadLayoutMiddleware(route: RouteLocationNormalized): Promise<void> {
  const { layout } = route.meta
  const normalizedLayoutName = layout || AppLayoutsEnum.default
  const fileName = AppLayoutToFileMap[normalizedLayoutName]
  const fileNameWithoutExtension = fileName.split('.vue')[0]

  const component = await import(`../../templates/${fileNameWithoutExtension}.vue`)
  route.meta.layoutComponent = component.default
}
