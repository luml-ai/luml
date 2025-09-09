import { ref, computed } from "vue";
import { defineStore } from "pinia";
import { dataforceApi } from "@/lib/api";
import type { OrbitSecret, CreateSecretPayload, UpdateSecretPayload } from "@/lib/api/orbit-secrets/interfaces";

export const useSecretsStore = defineStore("secrets", () => {
	const secretsList = ref < OrbitSecret[] > ([]);
	const creatorVisible = ref(false);

	const existingTags = computed((): string[] => {
		const tagsSet = secretsList.value.reduce((acc: Set < string > , item) => {
			item.tags?.forEach((tag: string) => acc.add(tag));
			return acc;
		}, new Set < string > ());
		return Array.from(tagsSet);
	});

	function showCreator() {
		creatorVisible.value = true;
	}

	function hideCreator() {
		creatorVisible.value = false;
	}

	async function loadSecrets(organizationId: number, orbitId: number) {
		const initialList = await dataforceApi.orbitSecrets.getSecrets(
			organizationId,
			orbitId,
		);

		if (initialList.length === 0) {
			secretsList.value = [];
			return;
		}

		const secretDetailPromises = initialList.map((secret) =>
			dataforceApi.orbitSecrets.getSecretById(organizationId, orbitId, secret.id),
		);

		const fullSecrets = await Promise.all(secretDetailPromises);
		secretsList.value = fullSecrets;
	}

	async function addSecret(
		organizationId: number,
		orbitId: number,
		payload: CreateSecretPayload,
	) {
		await dataforceApi.orbitSecrets.createSecret(organizationId, orbitId, payload);
		await loadSecrets(organizationId, orbitId);
	}

	async function updateSecret(
		organizationId: number,
		orbitId: number,
		payload: UpdateSecretPayload,
	) {
		await dataforceApi.orbitSecrets.updateSecret(organizationId, orbitId, payload);
		await loadSecrets(organizationId, orbitId);
	}

	async function deleteSecret(
		organizationId: number,
		orbitId: number,
		secretId: number,
	) {
		await dataforceApi.orbitSecrets.deleteSecret(organizationId, orbitId, secretId);
		secretsList.value = secretsList.value.filter(
			(secret) => secret.id !== secretId,
		);
	}

	async function getSecretById(
		organizationId: number,
		orbitId: number,
		secretId: number,
	) {
		return await dataforceApi.orbitSecrets.getSecretById(
			organizationId,
			orbitId,
			secretId,
		);
	}

	function reset() {
		secretsList.value = [];
		creatorVisible.value = false;
	}

	return {
		secretsList,
		creatorVisible,
		existingTags,
		showCreator,
		hideCreator,
		loadSecrets,
		addSecret,
		updateSecret,
		deleteSecret,
		getSecretById,
		reset,
	};
});