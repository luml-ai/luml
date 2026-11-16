import { test, expect } from './fixtures/test'

for (const width of [1440, 1100, 768, 375]) {
  for (const longProduct of ['Flow', 'Prisma']) {
    test(`home product icons stay at the bottom with long ${longProduct} content at ${width}px`, async ({
      page,
      apiMocks,
    }) => {
      await page.setViewportSize({ width, height: 1000 })
      await apiMocks.get('**/v1/auth/users/me', {
        status: 401,
        body: { detail: 'Not authenticated' },
      })
      await apiMocks.post('**/v1/auth/refresh', {
        status: 401,
        body: { detail: 'Not authenticated' },
      })
      await apiMocks.post('**/v1/auth/logout', {})
      await page.goto('/')

      const cards = page.locator('.product-cards article')
      await expect(cards).toHaveCount(2)
      await page.evaluate(() => document.fonts.ready)

      for (const product of ['Flow', 'Prisma']) {
        const card = cards.filter({
          has: page.getByRole('heading', { name: product, exact: true }),
        })
        await card.locator('.description').evaluate((element, long) => {
          element.textContent = long
            ? 'Explore data, run experiments, and iterate on models step by step. '.repeat(8)
            : 'Explore data.'
        }, product === longProduct)
      }

      const layouts = await cards.evaluateAll((elements) =>
        elements.map((element) => {
          const card = element.getBoundingClientRect()
          const main = element.querySelector('.main')!.getBoundingClientRect()
          const description = element.querySelector('.description')!.getBoundingClientRect()
          const divider = element.querySelector('.divider')!.getBoundingClientRect()
          const features = element.querySelector('.features')!.getBoundingClientRect()
          const style = getComputedStyle(element)
          return {
            top: card.top,
            iconsTop: features.top,
            iconsBottom: features.bottom,
            bottomGap: card.bottom - features.bottom,
            bottomInset: parseFloat(style.paddingBottom) + parseFloat(style.borderBottomWidth),
            contentBottom: main.bottom,
            descriptionHeight: description.height,
            dividerTop: divider.top,
            dividerBottom: divider.bottom,
          }
        }),
      )

      expect(layouts[longProduct === 'Flow' ? 0 : 1].descriptionHeight).toBeGreaterThan(
        layouts[longProduct === 'Flow' ? 1 : 0].descriptionHeight,
      )
      for (const layout of layouts) {
        expect(Math.abs(layout.bottomGap - layout.bottomInset)).toBeLessThanOrEqual(1)
        expect(layout.contentBottom).toBeLessThan(layout.dividerTop)
        expect(layout.dividerBottom).toBeLessThan(layout.iconsTop)
      }
      if (width > 1024) {
        expect(layouts[0].top).toBeCloseTo(layouts[1].top, 0)
        expect(layouts[0].iconsBottom).toBeCloseTo(layouts[1].iconsBottom, 0)
      }
    })
  }
}
