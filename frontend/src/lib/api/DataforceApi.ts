import axios from 'axios'
import type { AxiosInstance } from 'axios'
import type {
  IGetUserResponse,
  IPostLogoutRequest,
  IPostRefreshTokenRequest,
  IPostRefreshTokenResponse,
  IPostSignInRequest,
  IPostSignInResponse,
  IPostSignupRequest,
  IPostSignupResponse,
  TDeleteAccountResponse,
  IPostChangePasswordResponse,
  TPostLogoutResponse,
  IUpdateUserRequest,
  IPostForgotPasswordRequest,
  IPostForgotPasswordResponse,
  IGetGoogleLoginRequest,
  IResetPasswordRequest,
  ISendEmailRequest,
  Organization,
  Invitation,
  CreateOrganizationPayload,
  CreateOrganizationResponse,
  OrganizationDetails,
  AddMemberPayload,
  Member,
  UpdateMemberPayload,
  BaseDetailResponse,
  CreateInvitePayload,
  CreateOrbitPayload,
  Orbit,
  AddMemberToOrbitPayload,
  OrbitDetails,
  OrbitMember,
  UpdateOrbitPayload,
} from './DataforceApi.interfaces'
import { installDataforceInterceptors } from './DataforceApi.interceptors'
import type { OrbitRoleEnum } from '@/components/orbits/orbits.interfaces'
import { BucketSecretsApi } from './bucket-secrets'
import { OrbitCollectionsApi } from './orbit-collections'
import { MlModelsApi } from './orbit-ml-models'
import { ApiKeysApi } from './api-keys'
import { SatellitesApi } from './satellites'
import { OrbitSecretsApi } from './orbit-secrets'

export class DataforceApiClass {
  private api: AxiosInstance
  public bucketSecrets: BucketSecretsApi
  public orbitCollections: OrbitCollectionsApi
  public mlModels: MlModelsApi
  public apiKeys: ApiKeysApi
  public satellites: SatellitesApi
  public orbitSecrets: OrbitSecretsApi 

  constructor() {
    this.api = axios.create({
      baseURL: import.meta.env.VITE_DATAFORCE_API_URL,
      timeout: 10000,
    })

    installDataforceInterceptors(this.api)

    this.bucketSecrets = new BucketSecretsApi(this.api)
    this.orbitCollections = new OrbitCollectionsApi(this.api)
    this.mlModels = new MlModelsApi(this.api)
    this.apiKeys = new ApiKeysApi(this.api)
    this.satellites = new SatellitesApi(this.api)
    this.orbitSecrets = new OrbitSecretsApi(this.api)
  }

  public async signUp(data: IPostSignupRequest): Promise<IPostSignupResponse> {
    const { data: responseData } = await this.api.post('/auth/signup', data, {
      skipInterceptors: true,
    })

    return responseData
  }

  public async signIn(data: IPostSignInRequest): Promise<IPostSignInResponse> {
    const { data: responseData } = await this.api.post('/auth/signin', data, {
      skipInterceptors: true,
    })

    return responseData
  }

  public async googleLogin(params: IGetGoogleLoginRequest): Promise<IPostSignInResponse> {
    const { data } = await this.api.get('/auth/google/callback', {
      skipInterceptors: true,
      params,
    })

    return data
  }

  public async refreshToken(data: IPostRefreshTokenRequest): Promise<IPostRefreshTokenResponse> {
    const { data: responseData } = await this.api.post('/auth/refresh', data.refresh_token, {
      skipInterceptors: true,
    })

    return responseData
  }

  public async forgotPassword(
    data: IPostForgotPasswordRequest,
  ): Promise<IPostForgotPasswordResponse> {
    const { data: responseData } = await this.api.post('/auth/forgot-password', data.email, {
      skipInterceptors: true,
    })

    return responseData
  }

  public async getMe(): Promise<IGetUserResponse> {
    const { data: responseData } = await this.api.get('/auth/users/me')

    return responseData
  }

  public async updateUser(data: IUpdateUserRequest): Promise<IPostChangePasswordResponse> {
    const { data: responseData } = await this.api.patch('/auth/users/me', data)

    return responseData
  }

  public async deleteUser(): Promise<TDeleteAccountResponse> {
    const { data: responseData } = await this.api.delete('/auth/users/me')

    return responseData
  }

  public async logout(data: IPostLogoutRequest): Promise<TPostLogoutResponse> {
    const { data: responseData } = await this.api.post('/auth/logout', data)

    return responseData
  }

  public async resetPassword(data: IResetPasswordRequest) {
    await this.api.post('/auth/reset-password', data)
  }

  public async sendEmail(data: ISendEmailRequest) {
    await this.api.post('/stats/email-send', data, {
      skipInterceptors: true,
    })
  }

  public async getInvitations() {
    const { data: responseData } = await this.api.get<Invitation[]>('/users/me/invitations')
    return responseData
  }

  public async createInvite(organizationId: number, data: CreateInvitePayload) {
    const { data: responseData } = await this.api.post<Invitation>(`/organizations/${organizationId}/invitations`, data)
    return responseData
  }

  public async acceptInvitation(inviteId: number) {
    await this.api.post(`/users/me/invitations/${inviteId}/accept`)
  }

  public async rejectInvitation(inviteId: number) {
    await this.api.post(`/users/me/invitations/${inviteId}/reject`)
  }

  public async cancelInvitation(organizationId: number, inviteId: number) {
    await this.api.delete(`organizations/${organizationId}/invitations/${inviteId}`)
  }

  public async getOrganizations() {
    const { data: responseData } = await this.api.get<Organization[]>('/users/me/organizations')
    return responseData
  }

  public async createOrganization(data: CreateOrganizationPayload) {
    const { data: responseData } = await this.api.post<CreateOrganizationResponse>('/organizations', data)
    return responseData
  }

  public async updateOrganization(organizationId: number, data: CreateOrganizationPayload) {
    const { data: responseData } = await this.api.patch<OrganizationDetails>(`/organizations/${organizationId}`, data)
    return responseData
  }

  public async deleteOrganization(organizationId: number) {
    await this.api.delete(`organizations/${organizationId}`)
  }

  public async leaveOrganization(organizationId: number) {
    await this.api.delete(`organizations/${organizationId}/leave`)
  }

  public async getOrganization(id: number) {
    const { data: responseData } = await this.api.get<OrganizationDetails>(`/organizations/${id}`)
    return responseData
  }

  public async getOrganizationMembers(organizationId: number) {
    const { data: responseData } = await this.api.get<Member>(`/organizations/${organizationId}/members`)
    return responseData
  }

  public async addMemberToOrganization(organizationId: number, data: AddMemberPayload) {
    const { data: responseData } = await this.api.post<Member>(`/organizations/${organizationId}/members`, data)
    return responseData
  }

  public async updateOrganizationMember(organizationId: number, memberId: number, data: UpdateMemberPayload) {
    const { data: responseData } = await this.api.patch<Member>(`/organizations/${organizationId}/members/${memberId}`, data)
    return responseData
  }

  public async deleteMemberFormOrganization(organizationId: number, memberId: number) {
   const { data: responseData } = await this.api.delete<BaseDetailResponse>(`/organizations/${organizationId}/members/${memberId}`)
   return responseData
  }

  public async getOrganizationOrbits(organizationId: number) {
    const { data: responseData } = await this.api.get<Orbit[]>(`/organizations/${organizationId}/orbits`)
    return responseData
  }

  public async createOrbit(organization_id: number, data: CreateOrbitPayload) {
    const { data: responseData } = await this.api.post<Orbit>(`/organizations/${organization_id}/orbits`, data)
    return responseData
  }

  public async getOrbitDetails(organizationId: number, orbitId: number) {
    const { data: responseData } = await this.api.get<OrbitDetails>(`/organizations/${organizationId}/orbits/${orbitId}`)
    return responseData
  }

  public async updateOrbit(organizationId: number, data: UpdateOrbitPayload) {
    const { data: responseData } = await this.api.patch<Orbit>(`/organizations/${organizationId}/orbits/${data.id}`, data)
    return responseData
  }

  public async deleteOrbit(organizationId: number, orbitId: number) {
    const { data: responseData } = await this.api.delete<BaseDetailResponse>(`/organizations/${organizationId}/orbits/${orbitId}`)
    return responseData
  }

  public async getOrbitMembers(organizationId: number, orbitId: number) {
    const { data: responseData } = await this.api.get<OrbitMember>(`/organizations/${organizationId}/orbits/${orbitId}/members`)
    return responseData
  }

  public async addMemberToOrbit(organizationId: number, data: AddMemberToOrbitPayload) {
    const { data: responseData } = await this.api.post<OrbitMember>(`/organizations/${organizationId}/orbits/${data.orbit_id}/members`, data);
    return responseData
  }

  public async updateOrbitMember(organizationId: number, orbitId: number, data: { id: number, role: OrbitRoleEnum }) {
    const { data: responseData } = await this.api.patch<OrbitMember>(`/organizations/${organizationId}/orbits/${orbitId}/members/${data.id}`, data)
    return responseData
  }

  public async deleteOrbitMember(organizationId: number, orbitId: number, memberId: number) {
    const { data: responseData } = await this.api.delete<BaseDetailResponse>(`/organizations/${organizationId}/orbits/${orbitId}/members/${memberId}`)
    return responseData
  }
}
