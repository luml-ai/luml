import { test, expect } from './fixtures/test'

const USER_FIXTURE = {
  id: '3fa85f64-5717-4562-b3fc-2c963f66afa6',
  email: 'test@example.com',
  full_name: 'Test User',
  disabled: false,
  photo: '',
  has_api_key: false,
}

const SIGNIN_SUCCESS = {
  detail: 'ok',
  user_id: USER_FIXTURE.id,
}

test.describe('Auth — Sign in', () => {
  test.beforeEach(async ({ apiMocks }) => {
    await apiMocks.get('**/v1/auth/users/me', {
      status: 401,
      body: { detail: 'Not authenticated' },
    })
  })


  test.describe('Render', () => {
    test('renders sign-in form with all required elements', async ({ page }) => {
      await page.goto('/sign-in')

      await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible()
      await expect(page.getByText('Welcome to LUML')).toBeVisible()

      await expect(page.getByLabel('Email')).toBeVisible()
      await expect(page.locator('#password input')).toBeVisible()
      await expect(page.getByRole('button', { name: 'Sign in', exact: true })).toBeVisible()

      await expect(page.getByRole('link', { name: 'Sign up' })).toBeVisible()
      await expect(page.getByRole('link', { name: 'Forgot password?' })).toBeVisible()

      await expect(page.getByRole('button', { name: /Sign in with Google/i })).toBeVisible()
      await expect(page.getByRole('button', { name: /Sign in with Microsoft/i })).toBeVisible()
    })
  })


  test.describe('Successful login', () => {
    test('signs in with valid credentials and redirects to home', async ({ page, apiMocks }) => {
      await apiMocks.post('**/v1/auth/signin', SIGNIN_SUCCESS)
      await apiMocks.get('**/v1/auth/users/me', USER_FIXTURE)

      await page.goto('/sign-in')
      await page.getByLabel('Email').fill('test@example.com')
      await page.locator('#password input').fill('password123')

      const signinRequest = page.waitForRequest(
        (req) => req.url().includes('/v1/auth/signin') && req.method() === 'POST',
      )
      await page.getByRole('button', { name: 'Sign in', exact: true }).click()
      await signinRequest

      await expect(page).toHaveURL(/\/$/)
    })

    test('signs in and respects ?redirect= query param', async ({ page, apiMocks }) => {
      await apiMocks.post('**/v1/auth/signin', SIGNIN_SUCCESS)
      await apiMocks.get('**/v1/auth/users/me', USER_FIXTURE)

      await page.goto('/sign-in?redirect=/regression')
      await page.getByLabel('Email').fill('test@example.com')
      await page.locator('#password input').fill('password123')
      await page.getByRole('button', { name: 'Sign in', exact: true }).click()

      await expect(page).toHaveURL(/\/regression$/)
    })

    test('sends correct payload to /v1/auth/signin', async ({ page, apiMocks }) => {
      await apiMocks.post('**/v1/auth/signin', SIGNIN_SUCCESS)
      await apiMocks.get('**/v1/auth/users/me', USER_FIXTURE)

      await page.goto('/sign-in')
      await page.getByLabel('Email').fill('test@example.com')
      await page.locator('#password input').fill('password123')

      const requestPromise = page.waitForRequest(
        (req) => req.url().includes('/v1/auth/signin') && req.method() === 'POST',
      )
      await page.getByRole('button', { name: 'Sign in', exact: true }).click()
      const request = await requestPromise

      expect(request.postDataJSON()).toEqual({
        email: 'test@example.com',
        password: 'password123',
      })
    })
  })

  test.describe('Failed login', () => {
    test('shows backend error message on wrong credentials (401, string detail)', async ({
      page,
      apiMocks,
    }) => {
      await apiMocks.post('**/v1/auth/signin', {
        status: 401,
        body: { detail: 'Invalid credentials' },
      })

      await page.goto('/sign-in')
      await page.getByLabel('Email').fill('test@example.com')
      await page.locator('#password input').fill('wrongpassword')
      await page.getByRole('button', { name: 'Sign in', exact: true }).click()

      await expect(page.getByText('Invalid credentials')).toBeVisible()
      await expect(page).toHaveURL(/\/sign-in/)
    })

    test('shows first validation msg when backend returns 422 (array detail)', async ({
      page,
      apiMocks,
    }) => {
      await apiMocks.post('**/v1/auth/signin', {
        status: 422,
        body: {
          detail: [
            { loc: ['body', 'email'], msg: 'Email is not registered', type: 'value_error' },
          ],
        },
      })

      await page.goto('/sign-in')
      await page.getByLabel('Email').fill('unknown@example.com')
      await page.locator('#password input').fill('password123')
      await page.getByRole('button', { name: 'Sign in', exact: true }).click()

      await expect(page.getByText('Email is not registered')).toBeVisible()
    })

    test('shows fallback "Form is invalid" on unexpected error shape', async ({
      page,
      apiMocks,
    }) => {
      await apiMocks.post('**/v1/auth/signin', {
        status: 500,
        body: {},
      })

      await page.goto('/sign-in')
      await page.getByLabel('Email').fill('test@example.com')
      await page.locator('#password input').fill('password123')
      await page.getByRole('button', { name: 'Sign in', exact: true }).click()

      await expect(page.getByText('Form is invalid')).toBeVisible()
    })

    test('clears error message when user edits any input', async ({ page, apiMocks }) => {
      await apiMocks.post('**/v1/auth/signin', {
        status: 401,
        body: { detail: 'Invalid credentials' },
      })

      await page.goto('/sign-in')
      await page.getByLabel('Email').fill('test@example.com')
      await page.locator('#password input').fill('wrongpassword')
      await page.getByRole('button', { name: 'Sign in', exact: true }).click()
      await expect(page.getByText('Invalid credentials')).toBeVisible()
      await page.locator('#password input').fill('newpassword123')
      await expect(page.getByText('Invalid credentials')).toBeHidden()
    })
  })


  test.describe('Validation', () => {
    test('shows email + password errors when submitting empty form', async ({ page, apiMocks }) => {
      let signinCalled = false
      await apiMocks.post('**/v1/auth/signin', () => {
        signinCalled = true
        return SIGNIN_SUCCESS
      })

      await page.goto('/sign-in')
      await page.getByRole('button', { name: 'Sign in', exact: true }).click()

      await expect(page.getByText('Email is incorrect')).toBeVisible()
      await expect(page.getByText('Minimum password length 8 characters')).toBeVisible()
      expect(signinCalled).toBe(false)
    })

    test('shows email error on blur when email is invalid', async ({ page }) => {
      await page.goto('/sign-in')
      await page.getByLabel('Email').fill('not-an-email')
      await page.locator('#password input').click()
      await expect(page.getByText('Email is incorrect')).toBeVisible()
    })

    test('shows password error on blur when password is too short', async ({ page }) => {
      await page.goto('/sign-in')
      await page.locator('#password input').fill('short')
      await page.getByLabel('Email').click() 
      await expect(page.getByText('Minimum password length 8 characters')).toBeVisible()
    })

    test('does not call signin API when validation fails on submit', async ({
      page,
      apiMocks,
    }) => {
      let signinCalled = false
      await apiMocks.post('**/v1/auth/signin', () => {
        signinCalled = true
        return SIGNIN_SUCCESS
      })

      await page.goto('/sign-in')
      await page.getByLabel('Email').fill('not-an-email')
      await page.locator('#password input').fill('short')
      await page.getByRole('button', { name: 'Sign in', exact: true }).click()

      await expect(page.getByText('Email is incorrect')).toBeVisible()
      expect(signinCalled).toBe(false)
    })
  })


  test.describe('Navigation', () => {
    test('navigates to sign-up page', async ({ page }) => {
      await page.goto('/sign-in')
      await page.getByRole('link', { name: 'Sign up' }).click()
      await expect(page).toHaveURL(/\/sign-up$/)
    })

    test('navigates to forgot-password page', async ({ page }) => {
      await page.goto('/sign-in')
      await page.getByRole('link', { name: 'Forgot password?' }).click()
      await expect(page).toHaveURL(/\/forgot-password$/)
    })
  })
})