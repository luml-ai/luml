export interface BucketSecret {
  id: number
  endpoint: string
  bucket_name: string
  secure: boolean
  region: string
  cert_check: boolean
  organization_id: number
  created_at: Date
  updated_at: Date
}

export interface BucketSecretCreator {
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
