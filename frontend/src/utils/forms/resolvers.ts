import { z } from 'zod'
import { zodResolver } from '@primevue/forms/resolvers/zod'
import type { Orbit } from '@/lib/api/DataforceApi.interfaces'

export const signInResolver = zodResolver(
  z.object({
    email: z.string().email({ message: 'Email is incorrect' }),
    password: z.string().min(8, { message: 'Minimum password length 8 characters' }),
  }),
)

export const signUpResolver = zodResolver(
  z.object({
    username: z.string().min(3, { message: 'Username is required.' }),
    email: z.string().email('Email incorrect'),
    password: z.string().min(8, { message: 'Minimum password length 8 characters' }),
  }),
)

export const forgotPasswordResolver = zodResolver(
  z.object({
    email: z.string().email({ message: 'Email is incorrect' }),
  }),
)

export const resetPasswordResolver = zodResolver(
  z
    .object({
      password: z.string().min(8, { message: 'The password must be more than 8 characters' }),
      password_confirm: z
        .string()
        .min(8, { message: 'The password must be more than 8 characters' }),
    })
    .refine((data) => data.password === data.password_confirm, {
      message: 'Passwords must match',
      path: ['password_confirm'],
    }),
)

export const userSettingResolver = zodResolver(
  z.object({
    username: z.string().min(3, { message: 'Name must be more 3 characters' }),
    email: z.string().email({ message: 'Email is incorrect' }),
  }),
)

export const userChangePasswordResolver = zodResolver(
  z
    .object({
      current_password: z
        .string()
        .min(8, { message: 'The password must be more than 8 characters' }),
      new_password: z.string().min(8, { message: 'The password must be more than 8 characters' }),
      confirmPassword: z
        .string()
        .min(8, { message: 'The password must be more than 8 characters' }),
    })
    .refine((data) => data.new_password === data.confirmPassword, {
      message: 'Passwords must match',
      path: ['confirmPassword'],
    }),
)

export const orbitCreatorResolver = (orbitsList: Orbit[]) =>
  zodResolver(
    z.object({
      name: z
        .string()
        .min(1)
        .refine((val) => !orbitsList.find((orbit) => orbit.name === val), {
          message: 'An Orbit with this name already exists',
        }),
      members: z.array(
        z.object({
          user_id: z.number(),
          role: z.string(),
        }),
      ),
      bucket_secret_id: z.number(),
    }),
  )

export const collectionCreatorResolver = zodResolver(
  z.object({
    description: z.string(),
    name: z.string().min(1),
    collection_type: z.string().min(1),
  }),
)

export const collectionEditorResolver = zodResolver(
  z.object({
    name: z.string().min(1),
    bucket_secret_id: z.string(),
  }),
)

export const modelCreatorResolver = zodResolver(
  z.object({
    name: z.string().min(1),
    description: z.string(),
    file: z.instanceof(FileList).refine((file) => file?.length == 1, 'File is required.'),
    tags: z.array(z.string()),
  }),
)

export const modelEditorResolver = zodResolver(
  z.object({
    name: z.string().min(1),
    description: z.string(),
    tags: z.array(z.string()),
  }),
)

export const modelUploadResolver = zodResolver(
  z.object({
    orbit: z.number(),
    collection: z.number(),
    name: z.string().min(1),
    description: z.string(),
    tags: z.array(z.string()),
  }),
)

export const satellitesResolver = zodResolver(
  z.object({
    name: z.string().min(1),
    description: z.string().optional(),
  }),
)

export const createSecretResolver = zodResolver(
  z.object({
    name: z.string().trim().min(1, 'Name is required'),
    value: z.string().trim().min(1, 'Secret value is required'),
    tags: z.array(z.string()).optional().default([]),
  }),
)

export const updateSecretResolver = zodResolver(
  z.object({
    name: z.string().optional(),
    value: z.string().trim().optional(),
    tags: z.array(z.string()).optional().default([]),
  }),
)
