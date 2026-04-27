import { test as base, expect } from '@playwright/test'
import { createApiMocks, type ApiMocks } from './api-mocks'

type Fixtures = {
  apiMocks: ApiMocks
}

export const test = base.extend<Fixtures>({
  apiMocks: async ({ page }, use) => {
    const mocks = createApiMocks(page)
    await use(mocks)
  },
})

export { expect }