import { readFileSync } from 'node:fs'
import { chromium } from '@playwright/test'
import { mount } from '@vue/test-utils'
import { compileStyle, parse } from 'vue/compiler-sfc'
import { describe, expect, it } from 'vitest'
import FilePreviewHeader from '../FilePreviewHeader.vue'
import headerSource from '../FilePreviewHeader.vue?raw'

const lightTheme = readFileSync('src/demo/assets/theme/light-theme.css', 'utf8')
const darkTheme = readFileSync('src/demo/assets/theme/dark-theme.css', 'utf8')

describe('attachment preview header styles', () => {
  it('renders a visible border, background and emphasized file name in both themes', async () => {
    const wrapper = mount(FilePreviewHeader, {
      props: {
        fileName: 'report.csv',
        fileSize: 1024,
        filePath: 'reports/report.csv',
        isDownloading: false,
      },
      global: {
        stubs: { Button: true },
        directives: { tooltip: {} },
      },
    })
    const scopeId = Object.keys(wrapper.attributes()).find((key) => key.startsWith('data-v-'))!
    const { descriptor } = parse(headerSource)
    const { code } = compileStyle({
      source: descriptor.styles[0]!.content,
      filename: 'FilePreviewHeader.vue',
      id: scopeId,
      scoped: true,
    })

    let browser
    try {
      browser = await chromium.launch({ headless: true })
      const page = await browser.newPage()
      await page.setContent(wrapper.html())
      await page.addStyleTag({ content: `${lightTheme}\n${darkTheme}\n${code}` })

      for (const theme of [
        { name: 'light', border: 'rgb(226, 232, 240)', background: 'rgb(248, 250, 252)' },
        { name: 'dark', border: 'rgb(39, 39, 42)', background: 'rgb(10, 10, 10)' },
      ]) {
        await page.evaluate(
          (name) => document.documentElement.setAttribute('data-theme', name),
          theme.name,
        )
        const header = page.locator('.preview-header')
        const name = page.getByText('report.csv', { exact: true })

        await expect
          .poll(() => header.evaluate((el) => getComputedStyle(el).borderBottomWidth))
          .toBe('1px')
        expect(await header.evaluate((el) => getComputedStyle(el).borderBottomStyle)).toBe('solid')
        expect(await header.evaluate((el) => getComputedStyle(el).borderBottomColor)).toBe(
          theme.border,
        )
        expect(await header.evaluate((el) => getComputedStyle(el).backgroundColor)).toBe(
          theme.background,
        )
        expect(await name.evaluate((el) => getComputedStyle(el).fontWeight)).toBe('700')
        expect(await name.evaluate((el) => getComputedStyle(el).fontSize)).toBe('18px')
      }
    } finally {
      wrapper.unmount()
      await browser?.close()
    }
  }, 20_000)
})
