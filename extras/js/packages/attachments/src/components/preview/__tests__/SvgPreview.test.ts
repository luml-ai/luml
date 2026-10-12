import { Blob as NodeBlob } from 'node:buffer'
import { createServer } from 'node:http'
import { chromium } from '@playwright/test'
import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import SvgPreview from '../SvgPreview.vue'
import { processSvgContent } from '../../../utils/fileContentProcessors'
import hostileSvg from './fixtures/hostile.svg?raw'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('SVG attachment preview', () => {
  it('renders the preview URL in an image with an accessible file name', async () => {
    const wrapper = mount(SvgPreview, {
      props: { contentUrl: 'blob:preview', fileName: 'hostile.svg' },
    })

    expect(wrapper.find('object, iframe, embed, svg').exists()).toBe(false)
    expect(wrapper.get('img').attributes('src')).toBe('blob:preview')
    expect(wrapper.get('img').attributes('alt')).toBe('hostile.svg')

    await wrapper.setProps({ contentUrl: 'blob:next', fileName: 'next.svg' })
    expect(wrapper.get('img').attributes('src')).toBe('blob:next')
    expect(wrapper.get('img').attributes('alt')).toBe('next.svg')
    wrapper.unmount()
  })

  it.each([
    ['active content', hostileSvg],
    ['unterminated script', '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)'],
    ['empty content', ''],
  ])('preserves %s and normalizes its MIME type for image loading', async (_name, content) => {
    vi.stubGlobal('Blob', NodeBlob)
    const createObjectURL = vi.fn<(blob: Blob) => string>().mockReturnValue('blob:preview')
    vi.stubGlobal('URL', { createObjectURL })

    expect(await processSvgContent(new Blob([content], { type: 'text/plain' }))).toEqual({
      contentUrl: 'blob:preview',
    })
    const previewBlob = createObjectURL.mock.calls[0]![0]
    expect(previewBlob.type).toBe('image/svg+xml')
    expect(await previewBlob.text()).toBe(content)
  })

  it('loads the hostile SVG without executing its onload handler in Chromium', async () => {
    const server = createServer((_request, response) => {
      response.setHeader('Content-Type', 'text/html')
      response.end('<!doctype html><html><body></body></html>')
    })
    await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve))
    const address = server.address()
    if (!address || typeof address === 'string') throw new Error('Missing test server port')

    let browser
    const wrapper = mount(SvgPreview, {
      props: { contentUrl: 'blob:preview', fileName: 'hostile.svg' },
    })
    try {
      browser = await chromium.launch({ headless: true })
      const page = await browser.newPage()
      await page.goto(`http://127.0.0.1:${address.port}`)

      // verify the fixture executes when loaded as an active document.
      await page.evaluate((svg) => {
        const url = URL.createObjectURL(new window.Blob([svg], { type: 'image/svg+xml' }))
        const object = document.createElement('object')
        object.data = url
        object.type = 'image/svg+xml'
        document.body.append(object)
      }, hostileSvg)
      await page.waitForFunction(() => document.documentElement.hasAttribute('data-svg-onload'))

      await page.goto(`http://127.0.0.1:${address.port}`)
      await page.evaluate(
        ({ svg, markup }) => {
          const url = URL.createObjectURL(new window.Blob([svg], { type: 'image/svg+xml' }))
          document.body.innerHTML = markup.split('blob:preview').join(url)
        },
        { svg: hostileSvg, markup: wrapper.html() },
      )
      await page.waitForFunction(() => {
        const image = document.querySelector('img')
        return image?.complete && image.naturalWidth === 100
      })
      expect(await page.locator('html').getAttribute('data-svg-onload')).toBeNull()
      expect(await page.locator('html').getAttribute('data-svg-xss')).toBeNull()
    } finally {
      wrapper.unmount()
      await browser?.close()
      await new Promise<void>((resolve, reject) => {
        server.close((error) => (error ? reject(error) : resolve()))
      })
    }
  }, 20_000)
})
