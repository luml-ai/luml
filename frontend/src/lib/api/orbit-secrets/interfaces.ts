export interface OrbitSecret {
  id: number;
  name: string;
  value: string;
  orbit_id: number;
  created_at: string;
  updated_at: string;
  tags?: string[];
}

export type CreateSecretPayload = {
  name: string;
  value: string;
  tags?: string[];
};

export type UpdateSecretPayload = {
  id: number;
  name?: string;
  value?: string;
  tags?: string[];
}