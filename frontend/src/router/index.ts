import { createRouter, createWebHistory } from 'vue-router'
import { AppLayoutsEnum } from '@/templates/templates.types'
import { installMiddlewares } from './middlewares'

import HomePage from '@/pages/HomePage.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomePage,
    },
    {
      path: '/sign-up',
      name: 'sign-up',
      component: () => import('../pages/SignUpPage.vue'),
      meta: {
        layout: AppLayoutsEnum.clear,
      },
    },
    {
      path: '/sign-in',
      name: 'sign-in',
      component: () => import('../pages/SignInPage.vue'),
      meta: {
        layout: AppLayoutsEnum.clear,
      },
    },
    {
      path: '/forgot-password',
      name: 'forgot-password',
      component: () => import('../pages/ForgotPasswordPage.vue'),
      meta: {
        layout: AppLayoutsEnum.clear,
      },
    },
    {
      path: '/change-password',
      name: 'change-password',
      component: () => import('../pages/ChangePasswordPage.vue'),
      meta: {
        layout: AppLayoutsEnum.clear,
      },
    },
    {
      path: '/email-check',
      name: 'email-check',
      component: () => import('../pages/EmailCheckPage.vue'),
      meta: {
        layout: AppLayoutsEnum.clear,
      },
    },
    {
      path: '/email-confirmed',
      name: 'email-confirmed',
      component: () => import('../pages/EmailConfirmedPage.vue'),
      meta: {
        layout: AppLayoutsEnum.clear,
      },
    },
    {
      path: '/classification',
      name: 'classification',
      component: () => import('../pages/ClassificationPage.vue'),
      meta: {
        showInvalidMessage: 992,
      },
    },
    {
      path: '/regression',
      name: 'regression',
      component: () => import('../pages/RegressionPage.vue'),
      meta: {
        showInvalidMessage: 992,
      },
    },
    {
      path: '/runtime',
      name: 'runtime',
      component: () => import('../pages/RuntimePage.vue'),
      meta: {
        showInvalidMessage: 992,
      },
    },
    {
      path: '/prompt-fusion/:mode?',
      name: 'prompt-fusion',
      component: () => import('../pages/PromptFusionPage.vue'),
      meta: {
        mobileAvailable: false,
        showInvalidMessage: 992,
      },
    },
    {
      path: '/organization/:organizationId/orbits',
      name: 'orbits',
      component: () => import('../pages/orbits/index.vue'),
      meta: {
        requireAuth: true,
      },
    },
    {
      path: '/organization/:organizationId/orbit/:id',
      name: 'orbit',
      component: () => import('../pages/orbits/OrbitPage.vue'),
      meta: {
        requireAuth: true,
      },
      children: [
        {
          path: '',
          name: 'orbit-registry',
          component: () => import('../pages/orbits/OrbitRegistryView.vue'),
        },
        {
          path: 'deployments',
          name: 'orbit-deployments',
          component: () => import('../pages/orbits/OrbitDeploymentsView.vue'),
        },
        {
          path: 'satellites',
          name: 'orbit-satellites',
          component: () => import('../pages/orbits/OrbitSatellitesView.vue'),
        },
        {
          path: 'secrets',
          name: 'orbit-secrets',
          component: () => import('../pages/orbits/OrbitSecretsView.vue'),
        }
      ],
    },
    {
      path: '/organization/:organizationId/orbit/:id/collection/:collectionId',
      component: () => import('../pages/collection/CollectionPage.vue'),
      meta: {
        requireAuth: true,
      },
      children: [
        {
          path: '',
          name: 'collection',
          component: () => import('../pages/collection/ModelsListView.vue'),
        },
        {
          path: 'models/:modelId',
          component: () => import('../pages/collection/model/index.vue'),
          children: [
            {
              path: '',
              name: 'model',
              component: () => import('../pages/collection/model/DashboardView.vue'),
            },
            {
              path: 'card',
              name: 'model-card',
              component: () => import('../pages/collection/model/CardView.vue'),
            },
            {
              path: 'experiment-snapshot',
              name: 'model-snapshot',
              component: () => import('../pages/collection/model/SpanshotView.vue'),
            },
          ],
        },
        {
          path: 'compare',
          name: 'compare',
          component: () => import('../pages/collection/models-compare/CompareView.vue'),
        },
      ],
    },
    {
      path: '/notebooks',
      name: 'notebooks',
      component: () => import('../pages/NotebooksPage.vue'),
    },
    {
      path: '/data-agent',
      name: 'data-agent',
      component: () => import('../pages/DataAgentPage.vue'),
    },
    {
      path: '/organization/:id',
      name: 'organization',
      component: () => import('../pages/organization/index.vue'),
      meta: {
        requireAuth: true,
      },
      children: [
        {
          path: '',
          name: 'organization-members',
          component: () => import('../components/organizations/OrganizationMembers.vue'),
        },
        {
          path: 'orbits-list',
          name: 'organization-orbits',
          component: () => import('../components/organizations/OrganizationOrbits.vue'),
        },
        {
          path: 'buckets',
          name: 'organization-buckets',
          component: () => import('../components/organizations/registry/OrganizationRegistry.vue'),
        },
      ],
    },
    {
      path: '/:pathMatch(.*)*',
      name: '404',
      component: () => import('../pages/404Page.vue'),
    },
  ],
})

installMiddlewares(router)

export default router
