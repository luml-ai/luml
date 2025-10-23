export type Props = {
  title: string
  text: any
  initialType?: ContentTypeEnum
}

export enum ContentTypeEnum {
  yaml = 'yaml',
  markdown = 'markdown',
  raw = 'raw',
}
