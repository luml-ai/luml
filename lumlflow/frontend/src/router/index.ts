import { createRouter, createWebHistory } from 'vue-router'
import { ROUTE_NAMES, ROUTES } from './router.const'
import MainTemplate from '@/layouts/MainTemplate.vue'
import HomePage from '@/pages/home/HomePage.vue'
import ExperimentPage from '@/pages/experiment/ExperimentPage.vue'
import ExperimentDetailsPage from '@/pages/details/ExperimentDetailsPage.vue'
import OverviewView from '@/pages/details/OverviewView.vue'
import MetricsView from '@/pages/details/MetricsView.vue'
import TracesView from '@/pages/details/TracesView.vue'
import EvalsView from '@/pages/details/EvalsView.vue'
import AttachmentsView from '@/pages/details/AttachmentsView.vue'
import ExperimentsComparison from '@/pages/comparison/ExperimentsComparison.vue'
import GroupsComparisonPage from '@/pages/comparison/GroupsComparisonPage.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      component: MainTemplate,
      children: [
        {
          name: ROUTE_NAMES.HOME,
          path: ROUTES[ROUTE_NAMES.HOME],
          component: HomePage,
        },
        {
          name: ROUTE_NAMES.EXPERIMENT,
          path: ROUTES[ROUTE_NAMES.EXPERIMENT],
          component: ExperimentPage,
        },
        {
          name: ROUTE_NAMES.GROUPS_COMPARISON,
          path: ROUTES[ROUTE_NAMES.GROUPS_COMPARISON],
          component: GroupsComparisonPage,
        },
        {
          name: ROUTE_NAMES.EXPERIMENT_DETAILS,
          path: ROUTES[ROUTE_NAMES.EXPERIMENT_DETAILS],
          component: ExperimentDetailsPage,
          children: [
            {
              name: ROUTE_NAMES.EXPERIMENT_OVERVIEW,
              path: ROUTES[ROUTE_NAMES.EXPERIMENT_OVERVIEW],
              component: OverviewView,
            },
            {
              name: ROUTE_NAMES.EXPERIMENT_METRICS,
              path: ROUTES[ROUTE_NAMES.EXPERIMENT_METRICS],
              component: MetricsView,
            },
            {
              name: ROUTE_NAMES.EXPERIMENT_TRACES,
              path: ROUTES[ROUTE_NAMES.EXPERIMENT_TRACES],
              component: TracesView,
            },
            {
              name: ROUTE_NAMES.EXPERIMENT_EVALS,
              path: ROUTES[ROUTE_NAMES.EXPERIMENT_EVALS],
              component: EvalsView,
            },
            {
              name: ROUTE_NAMES.EXPERIMENT_ATTACHMENTS,
              path: ROUTES[ROUTE_NAMES.EXPERIMENT_ATTACHMENTS],
              component: AttachmentsView,
            },
          ],
        },
        {
          name: ROUTE_NAMES.EXPERIMENTS_COMPARISON,
          path: ROUTES[ROUTE_NAMES.EXPERIMENTS_COMPARISON],
          component: ExperimentsComparison,
        },
      ],
    },
  ],
})

export default router
