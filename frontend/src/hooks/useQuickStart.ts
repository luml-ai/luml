import type { Component } from 'vue'
import type { OrbitCollection } from '@/lib/api/orbit-collections/interfaces'
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { FolderDot, Folders, User } from 'lucide-vue-next'
import { PermissionEnum } from '@/lib/api/api.interfaces'
import { OrganizationRoleEnum } from '@/components/organizations/organization.interfaces'
import { useAuthStore } from '@/stores/auth'
import { useBucketsStore } from '@/stores/buckets'
import { useOrbitsStore } from '@/stores/orbits'
import { useOrganizationStore } from '@/stores/organization'

export enum QuickStartStepEnum {
  account = 'account',
  bucket = 'bucket',
  collection = 'collection',
}

export interface QuickStartStep {
  id: QuickStartStepEnum
  label: string
  icon: Component
  active: boolean
}

const DEFAULT_ORBIT_NAME = 'Default Orbit'

export const STEPS_CONFIG: Omit<QuickStartStep, 'active'>[] = [
  { id: QuickStartStepEnum.account, label: 'Create an account', icon: User },
  { id: QuickStartStepEnum.bucket, label: 'Link a storage bucket', icon: FolderDot },
  { id: QuickStartStepEnum.collection, label: 'Create a collection', icon: Folders },
]

export const useQuickStart = () => {
  const router = useRouter()
  const authStore = useAuthStore()
  const organizationStore = useOrganizationStore()
  const bucketsStore = useBucketsStore()
  const orbitsStore = useOrbitsStore()

  const isBucketDialogVisible = ref(false)
  const isCollectionDialogVisible = ref(false)
  const isBucketsSettled = ref(false)
  const bucketsOrganizationId = ref<string | null>(null)
  let bucketsRequestId = 0

  const organizationId = computed(() => organizationStore.currentOrganization?.id ?? null)

  const canCreateOrbit = computed(
    () =>
      !!organizationStore.currentOrganization?.permissions?.orbit?.includes(PermissionEnum.create),
  )

  const canManageBuckets = computed(() => {
    const role = organizationStore.currentOrganization?.role
    return role === OrganizationRoleEnum.owner || role === OrganizationRoleEnum.admin
  })

  const isBucketsLoaded = computed(
    () => !!organizationId.value && bucketsOrganizationId.value === organizationId.value,
  )

  const organizationBuckets = computed(() => (isBucketsLoaded.value ? bucketsStore.buckets : []))

  const collectionOrbit = computed(
    () => orbitsStore.currentOrbit ?? orbitsStore.orbitsList[0] ?? null,
  )

  const hasBucket = computed(
    () => organizationBuckets.value.length > 0 || orbitsStore.orbitsList.length > 0,
  )

  const hasCollection = computed(() =>
    orbitsStore.orbitsList.some((orbit) => orbit.total_collections > 0),
  )

  const activeStep = computed<QuickStartStepEnum | null>(() => {
    if (!authStore.isAuth) return QuickStartStepEnum.account
    if (!organizationId.value || !isBucketsSettled.value) return null
    if (!hasBucket.value) {
      return canManageBuckets.value && isBucketsLoaded.value ? QuickStartStepEnum.bucket : null
    }
    if (!hasCollection.value && (collectionOrbit.value || canCreateOrbit.value)) {
      return QuickStartStepEnum.collection
    }
    return null
  })

  const steps = computed<QuickStartStep[]>(() =>
    STEPS_CONFIG.map((step) => ({ ...step, active: step.id === activeStep.value })),
  )

  function runStep(stepId: QuickStartStepEnum) {
    if (stepId !== activeStep.value) return
    if (stepId === QuickStartStepEnum.account) {
      router.push({ name: 'sign-up' })
    } else if (stepId === QuickStartStepEnum.bucket) {
      isBucketDialogVisible.value = true
    } else {
      isCollectionDialogVisible.value = true
    }
  }

  function runActiveStep() {
    if (activeStep.value) runStep(activeStep.value)
  }

  async function createDefaultOrbit(orgId: string) {
    const bucket = organizationBuckets.value[0]
    if (!bucket) throw new Error('Storage bucket not found')
    const orbit = await orbitsStore.createOrbit(orgId, {
      name: DEFAULT_ORBIT_NAME,
      bucket_secret_id: bucket.id,
      members: [],
      notify: false,
    })
    orbitsStore.setCurrentOrbitId(orbit.id, orgId)
    return orbit
  }

  async function resolveCollectionRequestInfo() {
    const orgId = organizationId.value
    if (!orgId) throw new Error('Current organization not found')
    const orbit = collectionOrbit.value ?? (await createDefaultOrbit(orgId))
    return { organizationId: orgId, orbitId: orbit.id }
  }

  async function onCollectionCreated(
    collection: OrbitCollection,
    requestInfo: { organizationId: string; orbitId: string },
  ) {
    await router.push({
      name: 'collection',
      params: {
        organizationId: requestInfo.organizationId,
        id: requestInfo.orbitId,
        collectionId: collection.id,
      },
    })
    orbitsStore.loadOrbitsList(requestInfo.organizationId)
  }

  async function loadBuckets([id, canListBuckets]: [string | null, boolean]) {
    const requestId = ++bucketsRequestId
    isBucketsSettled.value = false
    bucketsOrganizationId.value = null
    if (!id || !authStore.isAuth) return
    if (!canListBuckets) {
      isBucketsSettled.value = true
      return
    }
    try {
      await bucketsStore.getBuckets(id)
      if (requestId === bucketsRequestId) bucketsOrganizationId.value = id
    } catch (e) {
      console.warn('Failed to load buckets', e)
    } finally {
      if (requestId === bucketsRequestId) isBucketsSettled.value = true
    }
  }

  watch([organizationId, canManageBuckets], loadBuckets, { immediate: true })

  return {
    steps,
    activeStep,
    runStep,
    runActiveStep,
    organizationId,
    collectionOrbit,
    isBucketDialogVisible,
    isCollectionDialogVisible,
    resolveCollectionRequestInfo,
    onCollectionCreated,
  }
}
