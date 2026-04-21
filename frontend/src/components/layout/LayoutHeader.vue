<template>
  <header id="header" class="header">
    <router-link :to="{ name: 'home' }" class="logo">
      <img src="@/assets/img/Logo_Full_light_mode.svg" alt="LUML" class="logo-img logo-light" />
      <img src="@/assets/img/Logo_Full_dark_mode.svg" alt="LUML" class="logo-img logo-dark" />
    </router-link>
    <div v-if="authStore.isAuth" class="logo-group">
      <OrganizationManagePopover />
      <span class="separator">/</span>
      <OrbitManagePopover />
    </div>

    <div v-if="isActivesVisible" class="actives">
      <user-toolbar v-if="authStore.isAuth" />
      <div v-else class="buttons">
        <d-button
          label="Log in"
          severity="contrast"
          variant="text"
          @click="$router.push({ name: 'sign-in', query: { redirect: $route.fullPath } })"
        />
        <d-button
          class="sign-up-button"
          label="Sign up"
          severity="primary"
          variant="text"
          @click="$router.push({ name: 'sign-up', query: { redirect: $route.fullPath } })"
        />
      </div>
      <d-button
        class="burger-button"
        variant="text"
        severity="contrast"
        @click="$emit('burgerClick')"
      >
        <template #icon>
          <transition>
            <X v-if="isBurgerOpen" :size="24" />
            <Menu v-else :size="24" />
          </transition>
        </template>
      </d-button>
    </div>
  </header>
</template>

<script setup lang="ts">
import UserToolbar from '../user/UserToolbar.vue'
import { useAuthStore } from '@/stores/auth'
import { X, Menu } from 'lucide-vue-next'
import OrganizationManagePopover from '../organizations/OrganizationManagePopover.vue'
import OrbitManagePopover from '../orbits/OrbitManagePopover.vue'

defineProps({
  isActivesVisible: {
    type: Boolean,
    default: true,
  },
  isBurgerOpen: {
    type: Boolean,
  },
})

type Emits = {
  (e: 'burgerClick'): void
}
defineEmits<Emits>()

const authStore = useAuthStore()
</script>

<style scoped>
.header {
  padding: 10px 16px;
  min-height: 64px;
  display: flex;
  align-items: center;
  gap: 40px;
  border-bottom: 1px solid var(--p-divider-border-color);
  background-color: var(--p-content-hover-background);
  flex-wrap: wrap;
}
.p-overflow-hidden .header {
  padding-right: calc(var(--p-scrollbar-width) + 16px);
}
.logo {
  height: 36px;
}
.logo-img {
  max-width: 202px;
  height: 36px;
}
.logo-group {
  display: flex;
  align-items: center;
}
.separator {
  color: var(--p-text-muted-color);
  font-size: 16px;
  padding: 0 2px;
  user-select: none;
}
.actives {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-left: auto;
}
.buttons {
  display: flex;
  gap: 11px;
  align-items: center;
}
.v-enter-active,
.v-leave-active {
  transition: width 0.5s ease;
}

.v-enter-from,
.v-leave-to {
  width: 0;
}

.logo-dark {
  display: none;
}

.burger-button {
  display: none;
}

@media (max-width: 992px) {
  .logo-group {
    order: 3;
    width: 100%;
    padding-top: 8px;
    border-top: 1px solid var(--p-divider-border-color);
    margin-top: 8px;
    justify-content: center;
  }
}

@media (max-width: 768px) {
  .burger-button {
    display: flex;
  }

  .sign-up-button {
    display: none;
  }
}

[data-theme='dark'] .logo-light {
  display: none;
}

[data-theme='dark'] .logo-dark {
  display: block;
}
</style>
