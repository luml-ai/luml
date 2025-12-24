export interface BucketSecret {
  type: BucketTypeEnum
  id: string
  endpoint: string
  bucket_name: string
  secure: boolean
  region: string
  cert_check: boolean
  organization_id: string
  created_at: Date
  updated_at: Date
}

export interface S3BucketFormData {
  type: BucketTypeEnum.s3
  endpoint: string
  bucket_name: string
  access_key?: string
  secret_key?: string
  session_token?: string
  secure?: boolean
  region?: string
  cert_check?: boolean
}

export interface BucketConnectionUrls {
  presigned_url: string
  download_url: string
  delete_url: string
}

export interface AzureBucketFormData {
  type: BucketTypeEnum.azure
  endpoint: string
  bucket_name: string
}

export enum BucketTypeEnum {
  s3 = 's3',
  azure = 'azure',
}

export type BucketFormData = S3BucketFormData | AzureBucketFormData

export type BucketFormDataWithId = BucketFormData & { id: string }
