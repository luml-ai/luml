import createDOMPurify from 'dompurify'
import { marked } from 'marked'

// Keep attachment-specific resource rules isolated from the host's other Markdown views.
const purifier = createDOMPurify()
if (purifier.isSupported) {
  purifier.addHook('uponSanitizeAttribute', (node, attr) => {
    if (node.namespaceURI === 'http://www.w3.org/2000/svg') {
      if (['href', 'xlink:href'].includes(attr.attrName))
        attr.keepAttr = /^#[\w.-]+$/.test(attr.attrValue)
      // SVG paint servers may reference a local gradient or marker.
      if (
        ['fill', 'stroke', 'marker-end', 'marker-start', 'marker-mid', 'clip-path'].includes(
          attr.attrName,
        )
      ) {
        attr.keepAttr =
          /^(?:[a-z]+|#[0-9a-f]+|(?:rgb|hsl)a?\([0-9.,% /+-]+\)|url\(#[\w.-]+\))$/i.test(
            attr.attrValue,
          )
      }
    }
    if (attr.attrName === 'src') {
      attr.keepAttr = node.nodeName === 'IMG' && /^data:image\//i.test(attr.attrValue)
    }
  })
}

export function renderMarkdown(source: string): string {
  const html = marked.parse(source, { async: false })
  return purifier.sanitize(html, {
    // These Markdown elements may have explicit links, but cannot load remote resources.
    ALLOWED_TAGS: [
      'svg',
      'g',
      'path',
      'rect',
      'circle',
      'ellipse',
      'line',
      'polyline',
      'polygon',
      'text',
      'tspan',
      'defs',
      'marker',
      'linearGradient',
      'radialGradient',
      'stop',
      'clipPath',
      'symbol',
      'use',
      'title',
      'desc',
      'a',
      'b',
      'blockquote',
      'br',
      'code',
      'dd',
      'del',
      'details',
      'div',
      'dl',
      'dt',
      'em',
      'h1',
      'h2',
      'h3',
      'h4',
      'h5',
      'h6',
      'hr',
      'i',
      'img',
      'input',
      'kbd',
      'li',
      'ol',
      'p',
      'pre',
      's',
      'span',
      'strong',
      'sub',
      'summary',
      'sup',
      'table',
      'tbody',
      'td',
      'th',
      'thead',
      'tr',
      'ul',
    ],
    ALLOWED_ATTR: [
      'id',
      'viewBox',
      'xmlns',
      'width',
      'height',
      'x',
      'y',
      'x1',
      'x2',
      'y1',
      'y2',
      'd',
      'points',
      'cx',
      'cy',
      'r',
      'rx',
      'ry',
      'transform',
      'fill',
      'stroke',
      'stroke-width',
      'opacity',
      'offset',
      'stop-color',
      'marker-end',
      'marker-start',
      'marker-mid',
      'clip-path',
      'text-anchor',
      'markerWidth',
      'markerHeight',
      'refX',
      'refY',
      'orient',
      'preserveAspectRatio',
      'xlink:href',
      'align',
      'alt',
      'checked',
      'class',
      'colspan',
      'disabled',
      'href',
      'rowspan',
      'src',
      'start',
      'title',
      'type',
    ],
  })
}
