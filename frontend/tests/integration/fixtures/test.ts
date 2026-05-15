import { test as base, expect } from '@playwright/test'
import { createApiMocks, type ApiMocks } from './api-mocks'
import { createWorkerMocks, type WorkerMocks } from './worker-mocks'

type Fixtures = {
  apiMocks: ApiMocks
  workerMocks: WorkerMocks
}

export const test = base.extend<Fixtures>({
  apiMocks: async ({ page }, use) => {
    await use(createApiMocks(page))
  },
  workerMocks: async ({ page }, use) => {
    await use(createWorkerMocks(page))
  },
})

export { expect }