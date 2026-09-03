import type { IWorkspaceFolderItem } from '@/components/workspace/folder/interface'
import { FLOW_FILE_EXTENSION } from '@/components/workspace/workspace.const'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { uuidv4 } from 'zod'

export const useWorkspaceStore = defineStore('workspace', () => {
  const currentDirectory = ref('')

  const items = ref<IWorkspaceFolderItem[]>([
    {
      id: '4',
      name: 'flow4.flow',
      type: 'flow',
      path: '/flow4',
      size: 400,
    },
    {
      id: '1',
      name: `Lorem Ipsum is simply dummy text of the printing and typesetting industry. Lorem Ipsum has been the industry's standard dummy text ever since 1966, when designers at Letraset and James Mosley, the librarian at St Bride Printing Library in London, took a 1914 Cicero translation and scrambled it to make dummy text for Letraset's Body Type sheets. It has survived not only many decades, but also the leap into electronic typesetting, remaining essentially unchanged. It was popularised thanks to these sheets and more recently with desktop publishing software like Aldus PageMaker and Microsoft Word including versions of Lorem Ipsum.`,
      type: 'folder',
      path: '/folder1',
      size: 4600,
    },
    {
      id: '2',
      name: 'folder2',
      type: 'folder',
      path: '/folder2',
      size: 237,
    },
    {
      id: '3',
      name: 'file3',
      type: 'file',
      path: '/file3',
      size: 134000,
    },
  ])

  const ITEM_TYPE_ORDER: Record<IWorkspaceFolderItem['type'], number> = {
    flow: 0,
    folder: 1,
    file: 2,
  }

  const sortedItems = computed(() => {
    return [...items.value].sort((a, b) => {
      const typeDiff = ITEM_TYPE_ORDER[a.type] - ITEM_TYPE_ORDER[b.type]
      if (typeDiff !== 0) return typeDiff
      return a.name.localeCompare(b.name)
    })
  })

  function deleteFlow(id: string) {
    items.value = items.value.filter((item) => item.id !== id)
  }

  function renameFlow(id: string, name: string) {
    const item = items.value.find((item) => item.id === id)
    if (item) {
      item.name = name
    }
  }

  function buildDuplicateFlowName(name: string): string {
    const baseName = name.endsWith(FLOW_FILE_EXTENSION)
      ? name.slice(0, -FLOW_FILE_EXTENSION.length)
      : name
    const existingNames = new Set(
      items.value.filter((item) => item.type === 'flow').map((item) => item.name),
    )

    let candidate = `${baseName} (copy)${FLOW_FILE_EXTENSION}`
    let copyNumber = 2
    while (existingNames.has(candidate)) {
      candidate = `${baseName} (copy ${copyNumber})${FLOW_FILE_EXTENSION}`
      copyNumber++
    }
    return candidate
  }

  function duplicateFlow(id: string) {
    const item = items.value.find((item) => item.id === id)
    if (item) {
      items.value.push({
        ...item,
        name: buildDuplicateFlowName(item.name),
        id: uuidv4().toString(),
      })
    }
  }

  function createFlow(name: string) {
    items.value.push({
      name: name,
      type: 'flow',
      id: uuidv4().toString(),
      path: `${currentDirectory.value}/${name}`,
      size: 0,
    })
  }

  return {
    items,
    sortedItems,
    deleteFlow,
    renameFlow,
    duplicateFlow,
    createFlow,
  }
})
