import JSZip from 'jszip'

export async function extractHtmlFromModelCardZip(zipData: ArrayBuffer): Promise<string> {
  const zip = await JSZip.loadAsync(zipData)
  const htmlFileName = Object.keys(zip.files).find(
    (name) => !zip.files[name].dir && name.endsWith('.html'),
  )

  if (!htmlFileName) {
    throw new Error('No HTML file found in model card archive')
  }

  let html = await zip.file(htmlFileName)!.async('string')

  if (!html.includes('<meta charset=')) {
    html = html.replace(/<head>/i, '<head>\n<meta charset="UTF-8">')
  }

  return html
}

export function createHtmlBlobUrl(html: string): string {
  const blob = new Blob([html], { type: 'text/html' })
  return URL.createObjectURL(blob)
}
