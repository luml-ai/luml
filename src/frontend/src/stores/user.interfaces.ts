export interface IUser {
  email: string
  full_name: string
  disabled: boolean
  auth_method: 'email' | 'google'
  id: string
  has_api_key: boolean
  photo?: string
}
