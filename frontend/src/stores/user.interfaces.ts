export interface IUser {
  email: string
  full_name: string
  disabled: boolean
  auth_method: 'EMAIL' | 'GOOGLE' | 'MICROSOFT'
  id: string
  has_api_key: boolean
  photo?: string
}
