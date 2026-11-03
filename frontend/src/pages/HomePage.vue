<template>
  <div class="home">
    <div class="intro">
      <HomeWelcome class="welcome" :show-quick-start="!!activeStep" @quick-start="runActiveStep" />
      <HomeAgentOnboarding class="onboarding" />
    </div>
    <div class="products">
      <div class="product-cards">
        <HomeProductCard v-for="product in products" :key="product.name" :product="product" />
      </div>
      <div class="connectors" aria-hidden="true">
        <img :src="connectorLeft" alt="" width="250.333" height="43.3333" class="connector left" />
        <img
          :src="connectorRight"
          alt=""
          width="249.333"
          height="43.3333"
          class="connector right"
        />
      </div>
      <HomeCoreCard :steps="steps" @run-step="runStep" />
    </div>
    <OrganizationBucketDialog v-model:visible="isBucketDialogVisible" show-info-block />
    <CollectionCreator
      v-if="organizationId"
      v-model:visible="isCollectionDialogVisible"
      :show-default-orbit-info="!collectionOrbit"
      :resolve-request-info="resolveCollectionRequestInfo"
      :after-create="onCollectionCreated"
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useToast } from 'primevue/usetoast'
import {
  Braces,
  FlaskConical,
  GitBranch,
  Notebook,
  SquareCheckBig,
  SquareKanban,
} from 'lucide-vue-next'

import HomeWelcome from '@/components/home/HomeWelcome.vue'
import HomeAgentOnboarding from '@/components/home/HomeAgentOnboarding.vue'
import HomeProductCard, { type HomeProduct } from '@/components/home/HomeProductCard.vue'
import HomeCoreCard from '@/components/home/HomeCoreCard.vue'
import OrganizationBucketDialog from '@/components/organizations/registry/OrganizationBucketDialog.vue'
import CollectionCreator from '@/components/orbits/tabs/registry/CollectionCreator.vue'

import { useQuickStart } from '@/hooks/useQuickStart'

import { useUserStore } from '@/stores/user'
import { passwordResetSuccessToast } from '@/lib/primevue/data/toasts'

import flowImage from '@/assets/img/home/flow.svg'
import prismaImage from '@/assets/img/home/prisma.svg'
import connectorLeft from '@/assets/img/home/connector-left.svg'
import connectorRight from '@/assets/img/home/connector-right.svg'

const docsUrl = import.meta.env.VITE_DOCS_URL

const products: HomeProduct[] = [
  {
    tag: 'Interactive',
    name: 'Flow',
    description:
      'You lead, agents assist. Explore data, run experiments, and iterate on models step by step.',
    learnMoreLink: `${docsUrl}/apps/lumlflow`,
    image: flowImage,
    features: [
      { label: 'Agentic notebooks', icon: Notebook },
      { label: 'Evals', icon: Braces },
      { label: 'Experiment tracking', icon: FlaskConical },
    ],
  },
  {
    tag: 'Autonomous',
    name: 'Prisma',
    description:
      'Agents lead, you steer. Set the goal and let agents plan the tasks, run them in parallel, and report back with results.',
    learnMoreLink: `${docsUrl}/apps/prisma/overview`,
    image: prismaImage,
    features: [
      { label: 'Task board', icon: SquareKanban },
      { label: 'Parallel runs', icon: SquareCheckBig },
      { label: 'Isolated worktrees', icon: GitBranch },
    ],
  },
]

const {
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
} = useQuickStart()

const userStore = useUserStore()
const toast = useToast()

onMounted(() => {
  if (userStore.isPasswordHasBeenChanged) toast.add(passwordResetSuccessToast)
})
</script>

<style scoped>
.home {
  padding: 32px 0;
  display: flex;
  flex-direction: column;
  gap: 109px;
}

.intro {
  display: flex;
  align-items: flex-start;
  gap: 44px;
}

.welcome {
  flex: 0 1 368px;
}

.onboarding {
  flex: 1 1 541px;
  min-width: 0;
}

.product-cards {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 24px;
}

.connectors {
  position: relative;
  height: 38px;
}

.connector {
  position: absolute;
  top: -2px;
  max-width: none;
}

.connector.left {
  right: calc(50% - 2.667px);
  transform: scaleX(-1);
}

.connector.right {
  left: calc(50% - 2.667px);
}

@media (max-width: 1024px) {
  .home {
    gap: 48px;
  }

  .intro {
    flex-direction: column;
    gap: 32px;
  }

  .welcome,
  .onboarding {
    flex: 0 0 auto;
    width: 100%;
  }

  .products {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .product-cards {
    grid-template-columns: 1fr;
    gap: 16px;
  }

  .connectors {
    display: none;
  }
}

@media (max-width: 768px) {
  .home {
    padding: 16px 0;
    gap: 32px;
  }
}
</style>
