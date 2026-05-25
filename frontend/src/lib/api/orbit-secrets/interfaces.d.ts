export interface OrbitSecret {
    id: string;
    name: string;
    value: string;
    orbit_id: string;
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
    id: string;
    name?: string;
    value?: string;
    tags?: string[];
};
