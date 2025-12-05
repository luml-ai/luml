import type { OrbitRoleEnum } from '@/components/orbits/orbits.interfaces'
import { OrganizationRoleEnum } from '@/components/organizations/organization.interfaces'

export interface BaseDetailResponse {
  detail: string
}

export interface IPostSignupRequest {
  email: string
  password: string
  full_name?: string
}

export interface IPostSignupResponse {
  detail: string
}

export interface IPostSignInRequest {
  email: string
  password: string
  grant_type?: string
  scope?: string
  client_id?: string
  client_secret?: string
}

export interface IPostSignInResponse {
  token: {
    access_token: string
    token_type: string
    refresh_token: string
  }
  user_id: number
}

export interface IPostRefreshTokenRequest {
  refresh_token: string
}

export interface IPostRefreshTokenResponse {
  access_token: string
  token_type: string
  refresh_token: string
}

export interface IPostChangePasswordRequest {
  current_password: string
  new_password: string
}

export interface IPostChangePasswordResponse {
  detail: string
}

export type TDeleteAccountResponse = string

export interface IGetUserResponse {
  email: string
  full_name: string
  disabled: boolean
  auth_method: 'email' | 'google'
  photo: string
  id: string
  has_api_key: boolean
}

export interface IPostLogoutRequest {
  refresh_token: string
}

export type TPostLogoutResponse = string

export interface IUpdateUserRequest {
  full_name?: string
  current_password?: string
  new_password?: string
  photo?: File
  email?: string
}

export interface IPostForgotPasswordRequest {
  email: string
}

export interface IPostForgotPasswordResponse {
  detail: string
}

export interface IGetGoogleLoginRequest {
  code: string
}

export interface IGetMicrosoftLoginRequest {
  code: string
}

export interface IResetPasswordRequest {
  reset_token: string
  new_password: string
}

export interface ISendEmailRequest {
  email: string
  description: string
}

export interface Organization {
  id: string
  name: string
  logo: string | null
  role: OrganizationRoleEnum
  created_at: Date
  updated_at: Date
  members_count: number
  permissions: OrganizationPermissions
}

export interface Invitation {
  id: string
  email: string
  role: OrganizationRoleEnum
  organization_id: string
  invited_by_user: Omit<IGetUserResponse, 'auth_method'>
  created_at: Date
  organization: Omit<Organization, 'role'>
}

export interface CreateOrganizationPayload {
  name: string
  logo: string
}

export interface CreateOrganizationResponse {
  id: string
  name: string
  logo: string
  created_at: Date
  updated_at: Date
}

export interface OrganizationDetails extends Omit<Organization, 'role'> {
  invites: Omit<Invitation, 'organization'>[]
  members: Member[]
  orbits: Orbit[]
  members_limit: number
  orbits_limit: number
  total_orbits: number
  total_members: number
  members_by_role: Record<OrganizationRoleEnum, number>
  satellites_limit: number
  model_artifacts_limit: number
  total_satellites: number
  total_model_artifacts: number
}

export interface Member {
  id: string
  organization_id: string
  role: OrganizationRoleEnum
  user: Omit<IGetUserResponse, 'auth_method'>
  created_at: Date
  updated_at: Date | null
}

export interface AddMemberPayload {
  user_id: string
  organization_id: string
  role: OrganizationRoleEnum
}

export interface UpdateMemberPayload {
  role: OrganizationRoleEnum
}

export interface CreateInvitePayload {
  email: string
  role: OrganizationRoleEnum
  organization_id: string
}

export interface Orbit {
  id: string
  name: string
  organization_id: string
  total_members: number
  created_at: Date
  updated_at: Date | null
  bucket_secret_id: string
  total_collections: number
  role: OrbitRoleEnum
  permissions: OrbitPermissions
}

export interface CreateOrbitPayload {
  name: string
  bucket_secret_id: string
  members: {
    user_id: string
    role: OrbitRoleEnum
  }[]
  notify: boolean
}

export interface UpdateOrbitPayload {
  id: string
  name: string
  bucket_secret_id: string
}

export interface AddMemberToOrbitPayload {
  user_id: string
  orbit_id: string
  role: OrbitRoleEnum
}

export interface OrbitDetails extends Orbit {
  members: OrbitMember[]
}

export interface OrbitMember extends Omit<Member, 'organization_id' | 'role'> {
  orbit_id: string
  role: OrbitRoleEnum
}

export interface OrganizationPermissions {
  organization: [
    PermissionEnum.read,
    PermissionEnum.update,
    PermissionEnum.delete,
    PermissionEnum.leave,
  ]
  organization_user: Omit<PermissionEnum, PermissionEnum.deploy>
  organization_invite: Omit<PermissionEnum, PermissionEnum.update & PermissionEnum.deploy>
  billing: [PermissionEnum.read, PermissionEnum.update]
  orbit: [PermissionEnum.create]
}

export interface OrbitPermissions {
  orbit: Omit<PermissionEnum, PermissionEnum.deploy>
  orbit_user: Omit<PermissionEnum, PermissionEnum.deploy>
  model: PermissionEnum
  collection: PermissionEnum
}

export enum PermissionEnum {
  list = 'list',
  read = 'read',
  create = 'create',
  update = 'update',
  delete = 'delete',
  deploy = 'deploy',
  leave = 'leave',
}
