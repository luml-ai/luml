<template>
  <header id="header" class="header">
    <router-link :to="{ name: 'home' }" class="logo">
      <img :src="mainLogo" alt="LUML" class="logo-img" />
    </router-link>
    <div v-if="isActivesVisible" class="actives">
      <user-toolbar v-if="authStore.isAuth" />
      <div v-else class="buttons">
        <d-button label="Log in" @click="$router.push({ name: 'sign-in' })" />
        <d-button
          class="sign-up-button"
          label="Sign up"
          severity="help"
          @click="$router.push({ name: 'sign-up' })"
        />
      </div>
      <d-button class="burger-button" @click="$emit('burgerClick')">
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
import { onBeforeMount, onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import logo from '@/assets/img/logo.svg'
import logoMobile from '@/assets/img/logo-mobile.svg'

import UserToolbar from '../user/UserToolbar.vue'
import { useAuthStore } from '@/stores/auth'

import { X, Menu } from 'lucide-vue-next'

type Emits = {
  (e: 'burgerClick'): void
}

defineProps({
  isActivesVisible: {
    type: Boolean,
    default: true,
  },
  isBurgerOpen: {
    type: Boolean,
  },
})

const emit = defineEmits<Emits>()

const authStore = useAuthStore()

const mainLogo = ref(logo)

function setLogo() {
  mainLogo.value = window.innerWidth > 768 ? logo : logoMobile
}

onBeforeMount(() => {
  setLogo()

  window.addEventListener('resize', setLogo)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', setLogo)
})
</script>

<style scoped>
.header {
  padding: 10px 16px;
  min-height: 64px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 40px;
  background-color: var(--p-primary-color);
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
.actives {
  display: flex;
  align-items: center;
  gap: 10px;
}
.buttons {
  display: flex;
  gap: 11px;
  align-items: center;
}

@media (min-width: 769px) {
  .burger-button {
    display: none;
  }
}

@media (max-width: 768px) {
  .sign-up-button {
    display: none;
  }
}

.v-enter-active,
.v-leave-active {
  transition: width 0.5s ease;
}

.v-enter-from,
.v-leave-to {
  width: 0;
}
</style>
