import { describe, expect, it } from 'vitest'
import {
  resetPasswordResolver,
  signInResolver,
  signUpResolver,
  userChangePasswordResolver,
} from './resolvers'

const validPassword = 'a'.repeat(8)
const rangeMessage = 'Password must be between 8 and 128 characters'

describe.each([
  {
    name: 'sign in',
    resolver: signInResolver,
    values: { email: 'user@example.com', password: validPassword },
    fields: ['password'],
  },
  {
    name: 'sign up',
    resolver: signUpResolver,
    values: { username: 'Test User', email: 'user@example.com', password: validPassword },
    fields: ['password'],
  },
  {
    name: 'reset password',
    resolver: resetPasswordResolver,
    values: { password: validPassword, password_confirm: validPassword },
    fields: ['password', 'password_confirm'],
  },
  {
    name: 'change password',
    resolver: userChangePasswordResolver,
    values: {
      current_password: validPassword,
      new_password: validPassword,
      confirmPassword: validPassword,
    },
    fields: ['current_password', 'new_password', 'confirmPassword'],
  },
])('$name password validation', ({ resolver, values, fields }) => {
  it.each([8, 128])('accepts matching passwords of length %i', async (length) => {
    const passwords = Object.fromEntries(fields.map((field) => [field, 'a'.repeat(length)]))
    const result = await resolver({ values: { ...values, ...passwords } })

    expect(result.errors).toEqual({})
  })

  describe.each(fields)('%s', (field) => {
    it.each([0, 7, 129])('rejects length %i with the allowed range', async (length) => {
      const result = await resolver({ values: { ...values, [field]: 'a'.repeat(length) } })

      expect(result.errors[field]).toEqual(
        expect.arrayContaining([expect.objectContaining({ message: rangeMessage })]),
      )
    })
  })
})

it.each([
  {
    resolver: resetPasswordResolver,
    values: { password: validPassword, password_confirm: 'different-password' },
    field: 'password_confirm',
  },
  {
    resolver: userChangePasswordResolver,
    values: {
      current_password: validPassword,
      new_password: validPassword,
      confirmPassword: 'different-password',
    },
    field: 'confirmPassword',
  },
])('requires matching confirmation in $field', async ({ resolver, values, field }) => {
  const result = await resolver({ values })

  expect(result.errors[field]).toEqual([
    expect.objectContaining({ message: 'Passwords must match' }),
  ])
})
