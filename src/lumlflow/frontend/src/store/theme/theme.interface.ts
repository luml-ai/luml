import { THEME } from './theme.const'

export type ThemeType = (typeof THEME)[keyof typeof THEME]
