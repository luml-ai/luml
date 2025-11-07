<template>
  <div class="wrapper">
    <div class="user-buttons">
      <UserInvitations></UserInvitations>
      <d-button severity="help" class="user-open-button" @click="toggleMenu">
        <d-avatar
          :label="getUserAvatar ? undefined : mainButtonLabel[0]"
          :image="getUserAvatar"
          shape="circle"
        ></d-avatar>
        <span>{{ mainButtonLabel }}</span>
        <chevron-down :size="14" />
      </d-button>
    </div>
    <d-dialog
      v-model:visible="isDialogVisible"
      position="topright"
      :closable="false"
      :draggable="false"
      modal
      dismissableMask
      :style="{ marginTop: '85px' }"
      class="modal-transparent-mask"
    >
      <template #header>
        <header class="header">
          <d-avatar
            :label="getUserAvatar ? undefined : getUserFullName?.[0] || getUserEmail?.[0]"
            :image="getUserAvatar"
            shape="circle"
            size="large"
          ></d-avatar>
          <div class="user-info">
            <div class="user-name">{{ getUserFullName }}</div>
            <div class="user-email">{{ getUserEmail }}</div>
          </div>
        </header>
      </template>
      <d-menu
        :model="menuItems"
        :style="{ backgroundColor: 'transparent', border: 'none', padding: '0', minWidth: '228px' }"
      >
        <template #item="{ item, props }">
          <div v-if="item.themeToggle" class="appearance">
            <span>{{ item.label }}</span>
            <UiThemeToggle v-model="theme" />
          </div>
          <a
            v-else-if="item.link"
            :href="item.link.href"
            :target="item.link.target"
            class="menu-item"
          >
            <span>{{ item.label }}</span>
          </a>
          <button type="button" v-else class="menu-item" v-bind="props.action" @click="item.action">
            <span>{{ item.label }}</span>
          </button>
        </template>
      </d-menu>
      <template #footer>
        <footer class="footer">
          <button type="button" class="logout-button" @click="onButtonLogoutClick">Log out</button>
        </footer>
      </template>
    </d-dialog>
  </div>
  <d-dialog v-model:visible="isSettingsPopupVisible" modal :style="{ width: '37rem' }">
    <template #header>
      <h2 style="font-weight: 600; font-size: 20px">ACCOUNT SETTINGS</h2>
    </template>
    <user-settings
      @show-change-password="onShowChangePassword"
      @close="isSettingsPopupVisible = !isSettingsPopupVisible"
    />
  </d-dialog>
  <d-dialog v-model:visible="isChangePasswordPopupVisible" modal :style="{ width: '37rem' }">
    <template #header>
      <h2 style="font-weight: 600; font-size: 20px">CHANGE PASSWORD</h2>
    </template>
    <user-change-password @success="onChangePasswordSuccess" />
  </d-dialog>
  <ApiKeyModal v-model:show="isApiKeyVisible" />
</template>

<script setup lang="ts">
import { useUserStore } from '@/stores/user'
import { storeToRefs } from 'pinia'
import { computed, ref, watch } from 'vue'
import UserSettings from './UserSettings.vue'
import UserChangePassword from './UserChangePassword.vue'
import UiThemeToggle from '../ui/UiThemeToggle.vue'
import { ChevronDown } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore, type Theme } from '@/stores/theme'
import { useToast } from 'primevue/usetoast'
import { passwordChangedSuccessToast } from '@/lib/primevue/data/toasts'
import UserInvitations from './UserInvitations.vue'
import ApiKeyModal from './ApiKeyModal.vue'

const userStore = useUserStore()
const authStore = useAuthStore()
const themeStore = useThemeStore()
const toast = useToast()

const theme = ref<Theme>(themeStore.getCurrentTheme)

const showChangePasswordSuccess = () => {
  toast.add(passwordChangedSuccessToast)
}

const { getUserEmail, getUserFullName, getUserAvatar } = storeToRefs(userStore)

const mainButtonLabel = computed(() => getUserFullName.value || 'Account')

const isDialogVisible = ref(false)
const isApiKeyVisible = ref(false)
const menuItems = ref([
  {
    label: 'Account',
    action: () => {
      isSettingsPopupVisible.value = true
    },
  },
  {
    label: 'Feedback',
    link: {
      target: '_blank',
      href: 'https://discord.com/invite/qVPPstSv9R',
    },
  },
  {
    label: 'Community',
    link: {
      target: '_blank',
      href: 'https://discord.com/invite/qVPPstSv9R',
    },
  },
  {
    label: 'API key',
    action: () => {
      isApiKeyVisible.value = true
    },
  },
  {
    label: 'Appearance',
    themeToggle: true,
  },
])

const isSettingsPopupVisible = ref(false)
const isChangePasswordPopupVisible = ref(false)

const toggleMenu = () => {
  isDialogVisible.value = !isDialogVisible.value
}

const onButtonLogoutClick = async () => {
  await authStore.logout()
}

const onShowChangePassword = () => {
  isSettingsPopupVisible.value = false
  isChangePasswordPopupVisible.value = true
}

const onChangePasswordSuccess = () => {
  isSettingsPopupVisible.value = true
  isChangePasswordPopupVisible.value = false

  setTimeout(() => {
    showChangePasswordSuccess()
  }, 100)
}

watch(theme, () => {
  themeStore.changeTheme()
})
</script>

<style scoped>
.wrapper {
  --menu-item-color: #334155;
}

.user-buttons {
  display: flex;
  align-items: center;
  gap: 16px;
}

.user-open-button {
  font-size: 0.875rem;
  font-weight: 500;
  padding: 7px 8px;
  display: flex;
  color: var(--p-text-color);
}

@media (any-hover: hover) {
  .user-open-button:not(:disabled):hover {
    color: var(--p-text-color);
  }
}

.content {
  padding: 24px 16px;
  border-radius: 8px;
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  display: flex;
  flex-direction: column;
  gap: 24px;
  width: 260px;
  margin-top: 24px;
  box-shadow: var(--card-shadow);
}

.header {
  width: 100%;
  display: flex;
  gap: 12px;
  align-items: center;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--p-divider-border-color);
}

.user-info-avatar {
  width: 42px;
  height: 42px;
}
.user-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.user-email {
  color: var(--p-text-muted-color);
  font-size: 14px;
}

.buttons {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.menu-item {
  padding: 7px;
  text-align: left;
  display: block;
  color: inherit;
  text-decoration: none;
}

.appearance {
  display: flex;
  justify-content: space-between;
  padding: 7px;
  gap: 5px;
  align-items: center;
}

.footer {
  width: 100%;
  padding-top: 24px;
  border-top: 1px solid var(--p-divider-border-color);
}

.logout-button {
  padding: 4px;
  color: var(--p-orange-600);
  cursor: pointer;
}
</style>
