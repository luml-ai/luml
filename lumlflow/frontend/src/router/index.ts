import { createRouter, createWebHistory } from 'vue-router'
import { ROUTES } from './router.const'
import MainTemplate from '@/layouts/MainTemplate.vue'
import HomePage from '@/pages/home/HomePage.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      component: MainTemplate,
      children: [
        {
          path: ROUTES.HOME,
          component: HomePage,
        },
      ],
    },
  ],
})

export default router
