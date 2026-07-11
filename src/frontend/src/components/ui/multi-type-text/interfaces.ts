export type Props = {
  title: string
  text: unknown
  initialType?: ContentTypeEnum
}

export enum ContentTypeEnum {
  yaml = 'yaml',
  markdown = 'markdown',
  raw = 'raw',
}
