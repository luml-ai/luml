import type { ModelAttachmentsProvider, FileNode, AttachmentContent } from './interfaces/interfaces'
import {
  TarAttachmentsProvider,
  type TarAttachmentsProviderConfig,
} from './models/TarAttachmentsProvider'

import ModelAttachments from './ModelAttachments.vue'

export { ModelAttachments }
export { TarAttachmentsProvider }
export type { TarAttachmentsProviderConfig }
export type { ModelAttachmentsProvider, FileNode, AttachmentContent }
export { default as FilePreview } from './components/FilePreview.vue'
export {
  getFileType,
  getFileExtension,
  getPreviewLanguage,
  EXTENSION_LANGUAGES,
} from './utils/fileTypes'
export type { FileType, PreviewLanguage } from './utils/fileTypes'
export { languageExtension } from './utils/codeHighlighting'
export { createPreviewStreamUrl, releasePreviewStreamUrl } from './utils/previewStream'
export type { PreviewSource, FilePreviewProps } from './interfaces/interfaces'
export { urlPreviewBytes } from './utils/previewBytes'
