<template>
  <div
    class="wrapper"
    :style="{ paddingLeft: sidebarWidth + 'px', paddingTop: headerSizes.height + 'px' }"
  >
    <UiClosablePlug
      v-if="plugStore.visible"
      text="Some operations may not behave correctly on mobile."
      :style="{
        position: 'fixed',
        top: headerSizes.height + 'px',
        left: sidebarSizes.width + 'px',
        right: 0,
        zIndex: 100,
      }"
      @close="plugStore.close"
    />
    <layout-header
      class="header"
      :is-burger-open="isBurgerOpen"
      @burger-click="() => (isBurgerOpen = !isBurgerOpen)"
    />
    <transition>
      <layout-sidebar
        v-show="isBurgerAvailable ? isBurgerOpen : true"
        class="sidebar"
        :mobile-sidebar-opened="isBurgerOpen"
      />
    </transition>
    <layout-footer class="footer" :style="`left:${sidebarWidth}px`" />
    <main class="page">
      <MobileNotAvailablePlug v-if="showMobileNotAvailablePlug" class="mobile-not-available-plug" />
      <slot v-else />
    </main>
  </div>
</template>

<script setup lang="ts">
import LayoutHeader from '@/components/layout/LayoutHeader.vue'
import LayoutSidebar from '@/components/layout/LayoutSidebar.vue'
import LayoutFooter from '@/components/layout/LayoutFooter.vue'
import MobileNotAvailablePlug from '@/components/plugs/MobileNotAvailablePlug.vue'
import UiClosablePlug from '@/components/ui/UiClosablePlug.vue'
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { usePlugStore } from '@/stores/plug'
import { useLayout } from '@/hooks/useLayout'
import { useWindowSize } from '@/hooks/useWindowSize'

const router = useRouter()
const route = useRoute()
const plugStore = usePlugStore()
const { headerSizes, sidebarSizes } = useLayout()
const { width: windowWidth } = useWindowSize()

const isBurgerOpen = ref(false)

const isBurgerAvailable = computed(() => windowWidth.value <= 768)
const mobileNotAvailable = computed(() => route.meta.mobileAvailable === false)
const showMobileNotAvailablePlug = computed(
  () => mobileNotAvailable.value && windowWidth.value <= 768,
)
const sidebarWidth = computed(() => sidebarSizes.value.width)

router.afterEach(() => {
  isBurgerOpen.value = false
})
</script>

<style scoped>
.wrapper {
  min-height: 100svh;
  padding-bottom: 60px;
  overflow-x: hidden;
}
.header {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
}
.sidebar {
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  z-index: 90;
}
.page {
  padding: 0 100px;
}
.footer {
  position: fixed;
  bottom: 0;
  right: 0;
  z-index: 80;
}

.v-enter-active,
.v-leave-active {
  transition: left 0.5s ease;
}

.v-enter-from,
.v-leave-to {
  left: -100%;
}

.mobile-not-available-plug {
  height: calc(100vh - 150px);
}

@media (max-width: 768px) {
  .wrapper {
    padding-left: 0 !important;
  }
  .footer {
    left: 0 !important;
  }
  .page {
    padding: 0 15px;
  }
}
</style>
