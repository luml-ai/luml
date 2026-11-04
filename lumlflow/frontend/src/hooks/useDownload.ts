import { ref, watch } from 'vue'
import { useObjectUrl } from '@vueuse/core'

export function useDownload() {
  const blob = ref<Blob | null>(null)
  const filename = ref('')
  const url = useObjectUrl(blob)

  watch(url, (value) => {
    if (!value) return
    const link = document.createElement('a')
    link.href = value
    link.download = filename.value
    link.click()
  })

  function download(content: BlobPart, name: string, type?: string) {
    filename.value = name
    blob.value = new Blob([content], type ? { type } : undefined)
  }

  return { download }
}
