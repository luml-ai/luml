<template>
  <div>
    <div class="mb-6">
      <div class="flex items-center justify-between gap-4">
        <!-- Message draws its border as an outline outside its box; main clips anything past its edges. -->
        <Message severity="warn" size="small" class="mx-(--p-message-border-width)"
          >This feature is in preview and can change.</Message
        >
        <OpenFlowsSummary />
      </div>
      <div class="flex items-center gap-4">
        <WorkspacePath class="min-w-0" @navigate="navigate" />
        <WorkspaceCreateMenu
          class="ml-auto mr-(--p-card-body-padding) shrink-0"
          @created-file="openFile"
        />
      </div>
    </div>
    <div :class="{ 'content-split': selectedFile }">
      <WorkspaceFolder
        :items="store.sortedItems"
        :selected-path="filePath"
        :before-operation="beforeOperation"
        @open-file="openFile"
        @navigate="navigate"
      />
      <WorkspaceFileViewer
        v-if="selectedFile"
        :key="selectedFile.path"
        ref="viewer"
        :file="selectedFile"
        :gone="gone"
        :locks="locks"
        :refresh-key="refreshKey"
        @dirty="dirty = $event"
        @saved="refreshListing"
        @reloaded="refreshListing"
        @close="openFile(undefined)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { useEventListener, useIntervalFn } from '@vueuse/core'
import { Message, useConfirm, useToast } from 'primevue'
import { computed, onMounted, onBeforeUnmount, ref, useTemplateRef, watch } from 'vue'
import {
  onBeforeRouteLeave,
  onBeforeRouteUpdate,
  useRoute,
  useRouter,
  type RouteLocationNormalized,
} from 'vue-router'
import { workspaceApi, WorkspaceRefusedError } from '@/api/slices/workspace/workspace.api'
import type {
  WorkspaceFile,
  WorkspaceFileLock,
  WorkspaceListing,
} from '@/api/slices/workspace/workspace.interface'
import { FlowStream, streamToken } from '@/api/streams/flow'
import WorkspaceFolder from '@/components/workspace/folder/WorkspaceFolder.vue'
import OpenFlowsSummary from '@/components/workspace/OpenFlowsSummary.vue'
import WorkspaceCreateMenu from '@/components/workspace/WorkspaceCreateMenu.vue'
import WorkspaceFileViewer from '@/components/workspace/WorkspaceFileViewer.vue'
import WorkspacePath from '@/components/workspace/WorkspacePath.vue'
import { baseName, parentDirectory } from '@/helpers/path'
import { OPEN_FLOWS_REFRESH_MS, useWorkspaceStore } from '@/store/workspace'
import { errorToast } from '@/toasts'

const route = useRoute()
const router = useRouter()
const toast = useToast()
const confirm = useConfirm()
const store = useWorkspaceStore()
const directory = computed(() =>
  typeof route.query.directory === 'string' ? route.query.directory : undefined,
)
const filePath = computed(() =>
  typeof route.query.file === 'string' ? route.query.file : undefined,
)
const selectedFile = ref<WorkspaceFile>()
const viewer = useTemplateRef('viewer')
const locks = ref<WorkspaceFileLock[]>([])
const listingMissing = ref(false)
const gone = ref(false)
const dirty = ref(false)
const changed = ref(0)
const refreshKey = ref(0)

function navigate(path: string) {
  return router.push({ query: { directory: path } })
}

function openFile(path?: string) {
  return router.push({ query: { directory: store.currentDirectory, file: path } })
}

async function confirmDiscard() {
  if (!dirty.value) return true
  return new Promise<boolean>((resolve) =>
    confirm.require({
      header: 'Discard unsaved changes?',
      message: `You have unsaved changes in ${selectedFile.value?.name}. Discard them and continue?`,
      acceptProps: { label: 'Discard and continue', severity: 'warn', variant: 'outlined' },
      rejectProps: { label: 'Cancel' },
      accept: () => resolve(true),
      reject: () => resolve(false),
      onHide: () => resolve(false),
    }),
  )
}

async function beforeOperation(path: string) {
  const separator = path.includes('/') ? '/' : '\\'
  const prefix = path.endsWith(separator) ? path : path + separator
  const affected = [filePath.value, viewer.value?.editTarget].some(
    (file) => file === path || file?.startsWith(prefix),
  )
  if (!affected) return true
  const accepted = await confirmDiscard()
  if (accepted) viewer.value?.discard()
  return accepted
}

// A newer navigation can cancel a slow one, even when it only changes the file.
const prepared = new WeakMap<RouteLocationNormalized, { page: WorkspaceListing; hidden: boolean }>()
const stopAfterNavigation = router.afterEach((to, from, failure) => {
  if (failure) return
  const listing = prepared.get(to)
  if (listing) {
    store.openListing(listing.page, listing.hidden)
    listingMissing.value = false
  }
  if (to.query.directory !== from.query.directory && dirty.value) viewer.value?.discard()
})
onBeforeUnmount(stopAfterNavigation)
onBeforeRouteLeave(confirmDiscard)
onBeforeRouteUpdate(async (to, from) => {
  if (to.query.file === from.query.file && to.query.directory === from.query.directory) return true
  if (!(await confirmDiscard())) return false
  if (
    to.query.directory !== from.query.directory &&
    to.query.directory !== store.currentDirectory
  ) {
    try {
      const path = typeof to.query.directory === 'string' ? to.query.directory : undefined
      const hidden = store.showHidden
      const page = await workspaceApi.listFlows(path, hidden, 0)
      prepared.set(to, { page, hidden })
    } catch (error) {
      toast.add(errorToast(error))
      return false
    }
  }
  return true
})
useEventListener(window, 'beforeunload', (event) => {
  if (dirty.value) event.preventDefault()
})

useIntervalFn(() => store.fetchOpenFlows(), OPEN_FLOWS_REFRESH_MS)
onMounted(async () => {
  const path = directory.value
  try {
    await store.fetchDirectory(path)
    if (!path && !directory.value && store.currentDirectory) {
      await router.replace({ query: { directory: store.currentDirectory, file: filePath.value } })
    }
  } catch (error) {
    toast.add(errorToast(error))
  }
})

// A bookmarked file can be hidden or beyond the visible listing pages. Look up
// its metadata independently, leaving the person's listing and page count intact.
watch(
  [filePath, () => store.files, changed, listingMissing],
  async ([path, files, version, missing], _, onCleanup) => {
    let active = true
    onCleanup(() => {
      active = false
    })
    if (selectedFile.value?.path !== path) {
      selectedFile.value = undefined
      gone.value = false
      dirty.value = false
    }
    if (!path) return
    if (!store.currentDirectory || store.isDirectoryLoading) return
    let file = missing ? undefined : files.find((entry) => entry.path === path)
    if (!file) {
      try {
        const result = await workspaceApi.fileInfo(path)
        if (!active) return
        file = result.file ?? undefined
      } catch (error) {
        if (active) toast.add(errorToast(error))
        return
      }
    }
    refreshKey.value = version
    gone.value = !file
    selectedFile.value = file ??
      selectedFile.value ?? {
        name: baseName(path),
        path,
        size: null,
        modified_at: '',
        is_symlink: false,
      }
  },
  { immediate: true },
)

async function refreshListing() {
  try {
    await store.refreshDirectory()
    listingMissing.value = false
  } catch (error) {
    if (
      error instanceof WorkspaceRefusedError &&
      error.kind === 'FlowError' &&
      error.message.startsWith('there is no directory')
    )
      listingMissing.value = true
    toast.add(errorToast(error))
  }
}

watch(
  [() => store.currentDirectory, filePath, () => store.isNotebookListing],
  ([folder, file, notebook], _, onCleanup) => {
    locks.value = []
    const token = streamToken()
    if (!folder || notebook || !token) return
    const stream = new FlowStream({ token })
    let timer: ReturnType<typeof setTimeout> | undefined
    let expiry: ReturnType<typeof setTimeout> | undefined
    function showLocks(snapshot: WorkspaceFileLock[], idleMs: number) {
      clearTimeout(expiry)
      const now = Date.now()
      locks.value = snapshot.filter((lock) => lock.last + idleMs > now)
      if (locks.value.length) {
        const next = locks.value.reduce(
          (first, lock) => Math.min(first, lock.last + idleMs),
          Infinity,
        )
        expiry = setTimeout(() => showLocks(locks.value, idleMs), next - now)
      }
    }
    let subscribedFile = file
    let active = true
    let running = false
    let pending = false
    let refreshFile = false
    let catchUp = true
    function queueRefresh(includesFile: boolean) {
      refreshFile ||= includesFile
      pending = true
      if (running || timer !== undefined) return
      timer = setTimeout(async () => {
        timer = undefined
        running = true
        pending = false
        const updateFile = refreshFile
        refreshFile = false
        await refreshListing()
        running = false
        if (!active) return
        if (updateFile) changed.value++
        if (pending) queueRefresh(false)
      }, 50)
    }
    stream.onStatus((status) => {
      if (status === 'open') catchUp = true
    })
    const off = stream.onFrame((frame) => {
      if (!('channel' in frame)) {
        if (subscribedFile) {
          subscribedFile = undefined
          stream.watchFiles(folder)
        } else toast.add(errorToast(new Error(frame.message)))
        return
      }
      if (frame.channel !== 'files') return
      if (frame.type === 'locks') {
        showLocks(frame.locks, frame.idle_after_s * 1000)
        if (catchUp) {
          catchUp = false
          queueRefresh(true)
        }
      } else if (frame.type === 'lagged') {
        catchUp = true
        stream.watchFiles(folder, subscribedFile)
      } else if (
        frame.directory === folder ||
        frame.path === file ||
        frame.directory === parentDirectory(file ?? '')
      ) {
        queueRefresh(frame.path === file || frame.path === frame.directory)
      }
    })
    stream.watchFiles(folder, subscribedFile)
    stream.connect()
    onCleanup(() => {
      active = false
      off()
      clearTimeout(expiry)
      clearTimeout(timer)
      stream.close()
    })
  },
  { immediate: true },
)
</script>

<style scoped>
.content-split {
  display: grid;
  grid-template-columns: minmax(0, 400px) minmax(0, 1fr);
  gap: 1rem;
  align-items: start;
}
.content-split > .viewer {
  position: sticky;
  top: 0;
}
</style>
