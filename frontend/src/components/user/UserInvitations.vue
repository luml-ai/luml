<template>
  <div class="user-notification">
    <div v-if="invitationsStore.invitations.length" class="user-notification__circle"></div>
    <d-button rounded severity="help" class="bell-button" @click="visible = true">
      <template #icon>
        <Bell :size="12" />
      </template>
    </d-button>

    <Dialog
      v-model:visible="visible"
      modal
      :draggable="false"
      :style="{ maxWidth: '1000px', width: '100%', padding: '18px' }"
    >
      <template #header>
        <div>
          <h3 class="title">invitation center</h3>
        </div>
      </template>
      <h4 class="sub-title">Organization collaborators have access to specific orbits.</h4>
      <InvitationsList />
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Bell } from 'lucide-vue-next'
import { Dialog } from 'primevue'
import { useInvitationsStore } from '@/stores/invitations'
import InvitationsList from './InvitationsList.vue'

const invitationsStore = useInvitationsStore()

const visible = ref(false)
</script>

<style scoped>
.user-notification {
  position: relative;
}
.user-notification__circle {
  position: absolute;
  top: 0;
  right: 0;
  width: 10px;
  height: 10px;
  background-color: var(--p-badge-success-background);
  border-radius: 50%;
  z-index: 2;
}
.title {
  font-weight: 600;
  text-transform: uppercase;
  font-size: 20px;
}
.sub-title {
  color: var(--p-text-muted-color);
  margin-bottom: 28px;
}
.bell-button :deep(svg) {
  color: var(--p-button-text-contrast-color);
}
</style>
