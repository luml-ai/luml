export enum AppLayoutsEnum {
  default = 'default',
  clear = 'clear',
}

export const AppLayoutToFileMap: Record<AppLayoutsEnum, string> = {
  default: 'DefaultTemplate.vue',
  clear: 'ClearTemplate.vue',
}
