import { defineStore } from "pinia";
import { dataforceApi } from "@/lib/api";
import type { OrbitSecret } from "@/lib/api/orbit-secrets/interfaces";

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
};

interface ISecretsState {
  secretsList: OrbitSecret[];
  loading: boolean;
  error: string | null;
  creatorVisible: boolean;
}

export const useSecretsStore = defineStore("secrets", {
  state: (): ISecretsState => ({
    secretsList: [],
    loading: false,
    error: null,
    creatorVisible: false,
  }),
    getters: {
    /**
     * @param state 
     */
    existingTags(state): string[] {
      const tagsSet = state.secretsList.reduce((acc: Set<string>, item) => {
        item.tags?.forEach((tag: string) => acc.add(tag));
        return acc;
      }, new Set<string>());
      return Array.from(tagsSet);
    },
  },

  actions: {
    showCreator() {
      this.creatorVisible = true;
    },

    hideCreator() {
      this.creatorVisible = false;
    },

    async loadSecrets(organizationId: number, orbitId: number) {
      this.loading = true;
      this.error = null;
      try {
        const initialList = await dataforceApi.orbitSecrets.getSecrets(
          organizationId,
          orbitId,
        );

        if (initialList.length === 0) {
          this.secretsList = [];
          return;
        }

        const secretDetailPromises = initialList.map((secret) =>
          dataforceApi.orbitSecrets
            .getSecretById(organizationId, orbitId, secret.id)
            .catch((e) => {
              return null;
            }),
        );
        const fullSecretsWithPossibleNulls =
          await Promise.all(secretDetailPromises);
        this.secretsList = fullSecretsWithPossibleNulls.filter(
          (secret) => secret !== null,
        ) as OrbitSecret[];
      } catch (e: any) {
        this.error = e.message || "Failed to load secrets";
        this.secretsList = [];
        throw e;
      } finally {
        this.loading = false;
      }
    },

    async addSecret(
      organizationId: number,
      orbitId: number,
      payload: CreateSecretPayload,
    ) {
      try {
        await dataforceApi.orbitSecrets.createSecret(
          organizationId,
          orbitId,
          payload,
        );
        await this.loadSecrets(organizationId, orbitId);
      } catch (e: any) {
        this.error = e.message || "Failed to create secret";
        throw e;
      }
    },

    async updateSecret(
      organizationId: number,
      orbitId: number,
      payload: UpdateSecretPayload,
    ) {
      try {
        await dataforceApi.orbitSecrets.updateSecret(
          organizationId,
          orbitId,
          payload,
        );
        await this.loadSecrets(organizationId, orbitId);
      } catch (e: any) {
        this.error = e.message || "Failed to update secret";
        throw e;
      }
    },

    async deleteSecret(
      organizationId: number,
      orbitId: number,
      secretId: number,
    ) {
      try {
        await dataforceApi.orbitSecrets.deleteSecret(
          organizationId,
          orbitId,
          secretId,
        );
        this.secretsList = this.secretsList.filter(
          (secret) => secret.id !== secretId,
        );
      } catch (e: any) {
        this.error = e.message || "Failed to delete secret";
        throw e;
      }
    },

    async getSecretById(
      organizationId: number,
      orbitId: number,
      secretId: number,
    ) {
      this.loading = true;
      this.error = null;
      try {
        const secret = await dataforceApi.orbitSecrets.getSecretById(
          organizationId,
          orbitId,
          secretId,
        );
        return secret as OrbitSecret;
      } catch (e: any) {
        this.error = e.message || "Failed to load secret";
        console.error("Get secret by ID error:", e);
        throw e;
      } finally {
        this.loading = false;
      }
    },

    reset() {
      this.secretsList = [];
      this.error = null;
      this.loading = false;
      this.creatorVisible = false;
    },
  },
});
