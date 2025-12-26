import axios from 'axios'
import type { AxiosInstance } from 'axios'
import type {
  IGetUserResponse,
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
  IGetMicrosoftLoginRequest,
} from './api.interfaces'
import { installInterceptors } from './api.interceptors'
import type { OrbitRoleEnum } from '@/components/orbits/orbits.interfaces'
import { BucketSecretsApi } from './bucket-secrets'
import { OrbitCollectionsApi } from './orbit-collections'
import { MlModelsApi } from './orbit-ml-models'
import { ApiKeysApi } from './api-keys'
import { SatellitesApi } from './satellites'
import { OrbitSecretsApi } from './orbit-secrets'
import { DeploymentsApi } from './deployments'

export class ApiClass {
  private api: AxiosInstance
  public bucketSecrets: BucketSecretsApi
  public orbitCollections: OrbitCollectionsApi
  public mlModels: MlModelsApi
  public apiKeys: ApiKeysApi
  public satellites: SatellitesApi
  public orbitSecrets: OrbitSecretsApi
  public deployments: DeploymentsApi

  constructor() {
    this.api = axios.create({
      baseURL: import.meta.env.VITE_API_URL,
      timeout: 10000,
      withCredentials: true,
    })

    installInterceptors(this.api)

    this.bucketSecrets = new BucketSecretsApi(this.api)
    this.orbitCollections = new OrbitCollectionsApi(this.api)
    this.mlModels = new MlModelsApi(this.api)
    this.apiKeys = new ApiKeysApi(this.api)
    this.satellites = new SatellitesApi(this.api)
    this.orbitSecrets = new OrbitSecretsApi(this.api)
    this.deployments = new DeploymentsApi(this.api)
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

  public async microsoftLogin(params: IGetMicrosoftLoginRequest): Promise<IPostSignInResponse> {
    const { data } = await this.api.get('/auth/microsoft/callback', {
      skipInterceptors: true,
      params,
    })

    return data
  }

  public async refreshToken(): Promise<IPostRefreshTokenResponse> {
    const { data: responseData } = await this.api.post(
      '/auth/refresh',
      {},
      {
        skipInterceptors: true,
      },
    )

    return responseData
  }

  public async forgotPassword(
    data: IPostForgotPasswordRequest,
  ): Promise<IPostForgotPasswordResponse> {
    const { data: responseData } = await this.api.post('/auth/forgot-password', data, {
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

  public async logout(): Promise<TPostLogoutResponse> {
    const { data: responseData } = await this.api.post('/auth/logout', {})
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

  public async createInvite(organizationId: string, data: CreateInvitePayload) {
    const { data: responseData } = await this.api.post<Invitation>(
      `/organizations/${organizationId}/invitations`,
      data,
    )
    return responseData
  }

  public async acceptInvitation(inviteId: string) {
    await this.api.post(`/users/me/invitations/${inviteId}/accept`)
  }

  public async rejectInvitation(inviteId: string) {
    await this.api.post(`/users/me/invitations/${inviteId}/reject`)
  }

  public async cancelInvitation(organizationId: string, inviteId: string) {
    await this.api.delete(`organizations/${organizationId}/invitations/${inviteId}`)
  }

  public async getOrganizations() {
    const { data: responseData } = await this.api.get<Organization[]>('/users/me/organizations')
    return responseData
  }

  public async createOrganization(data: CreateOrganizationPayload) {
    const { data: responseData } = await this.api.post<CreateOrganizationResponse>(
      '/organizations',
      data,
    )
    return responseData
  }

  public async updateOrganization(organizationId: string, data: CreateOrganizationPayload) {
    const { data: responseData } = await this.api.patch<OrganizationDetails>(
      `/organizations/${organizationId}`,
      data,
    )
    return responseData
  }

  public async deleteOrganization(organizationId: string) {
    await this.api.delete(`organizations/${organizationId}`)
  }

  public async leaveOrganization(organizationId: string) {
    await this.api.delete(`organizations/${organizationId}/leave`)
  }

  public async getOrganization(id: string) {
    const { data: responseData } = await this.api.get<OrganizationDetails>(`/organizations/${id}`)
    return responseData
  }

  public async getOrganizationMembers(organizationId: string) {
    const { data: responseData } = await this.api.get<Member>(
      `/organizations/${organizationId}/members`,
    )
    return responseData
  }

  public async addMemberToOrganization(organizationId: string, data: AddMemberPayload) {
    const { data: responseData } = await this.api.post<Member>(
      `/organizations/${organizationId}/members`,
      data,
    )
    return responseData
  }

  public async updateOrganizationMember(
    organizationId: string,
    memberId: string,
    data: UpdateMemberPayload,
  ) {
    const { data: responseData } = await this.api.patch<Member>(
      `/organizations/${organizationId}/members/${memberId}`,
      data,
    )
    return responseData
  }

  public async deleteMemberFormOrganization(organizationId: string, memberId: string) {
    const { data: responseData } = await this.api.delete<BaseDetailResponse>(
      `/organizations/${organizationId}/members/${memberId}`,
    )
    return responseData
  }

  public async getOrganizationOrbits(organizationId: string) {
    const { data: responseData } = await this.api.get<Orbit[]>(
      `/organizations/${organizationId}/orbits`,
    )
    return responseData
  }

  public async createOrbit(organization_id: string, data: CreateOrbitPayload) {
    const { data: responseData } = await this.api.post<Orbit>(
      `/organizations/${organization_id}/orbits`,
      data,
    )
    return responseData
  }

  public async getOrbitDetails(organizationId: string, orbitId: string) {
    const { data: responseData } = await this.api.get<OrbitDetails>(
      `/organizations/${organizationId}/orbits/${orbitId}`,
    )
    return responseData
  }

  public async updateOrbit(organizationId: string, data: UpdateOrbitPayload) {
    const { data: responseData } = await this.api.patch<Orbit>(
      `/organizations/${organizationId}/orbits/${data.id}`,
      data,
    )
    return responseData
  }

  public async deleteOrbit(organizationId: string, orbitId: string) {
    const { data: responseData } = await this.api.delete<BaseDetailResponse>(
      `/organizations/${organizationId}/orbits/${orbitId}`,
    )
    return responseData
  }

  public async getOrbitMembers(organizationId: string, orbitId: string) {
    const { data: responseData } = await this.api.get<OrbitMember>(
      `/organizations/${organizationId}/orbits/${orbitId}/members`,
    )
    return responseData
  }

  public async addMemberToOrbit(organizationId: string, data: AddMemberToOrbitPayload) {
    const { data: responseData } = await this.api.post<OrbitMember>(
      `/organizations/${organizationId}/orbits/${data.orbit_id}/members`,
      data,
    )
    return responseData
  }

  public async updateOrbitMember(
    organizationId: string,
    orbitId: string,
    data: { id: string; role: OrbitRoleEnum },
  ) {
    const { data: responseData } = await this.api.patch<OrbitMember>(
      `/organizations/${organizationId}/orbits/${orbitId}/members/${data.id}`,
      data,
    )
    return responseData
  }

  public async deleteOrbitMember(organizationId: string, orbitId: string, memberId: string) {
    const { data: responseData } = await this.api.delete<BaseDetailResponse>(
      `/organizations/${organizationId}/orbits/${orbitId}/members/${memberId}`,
    )
    return responseData
  }
}
