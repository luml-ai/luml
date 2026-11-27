import type { App, Component, InjectionKey } from 'vue'
import type { Pinia } from 'pinia'
import type { Router, RouteRecordRaw } from 'vue-router'

export interface ChildRoute {
  parent: string
  route: RouteRecordRaw
}

export type ExtensionRoute = RouteRecordRaw | ChildRoute

export interface AppExtension {
  routes?: ExtensionRoute[]
  outlets?: Record<string, Component | Component[]>
  install?: (app: App, router: Router, pinia: Pinia) => void
}

export type OutletRegistry = ReadonlyMap<string, Component[]>

export const outletRegistryKey: InjectionKey<OutletRegistry> = Symbol('extension-outlets')

export function installExtensions(
  app: App,
  router: Router,
  pinia: Pinia,
  extensions: AppExtension[],
): void {
  const outlets = new Map<string, Component[]>()
  for (const extension of extensions) {
    for (const entry of extension.routes ?? []) {
      if ('parent' in entry) {
        if (!router.hasRoute(entry.parent)) {
          throw new Error(`Extension route parent "${entry.parent}" is not a registered route name`)
        }
        router.addRoute(entry.parent, entry.route)
      } else {
        router.addRoute(entry)
      }
    }
    for (const [name, components] of Object.entries(extension.outlets ?? {})) {
      const added = Array.isArray(components) ? components : [components]
      outlets.set(name, [...(outlets.get(name) ?? []), ...added])
    }
    extension.install?.(app, router, pinia)
  }
  app.provide(outletRegistryKey, outlets)
}
