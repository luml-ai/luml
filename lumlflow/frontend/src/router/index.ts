import { createRouter, createWebHistory } from 'vue-router'
import { ROUTE_NAMES, ROUTES } from './router.const'
import MainTemplate from '@/layouts/MainTemplate.vue'
import HomePage from '@/pages/home/HomePage.vue'
import ExperimentPage from '@/pages/experiment/ExperimentPage.vue'

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
      ],
    },
  ],
})

export default router
