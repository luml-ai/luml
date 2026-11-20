import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import FileTree from '../FileTree.vue'
import type { FileNode } from '../../interfaces/interfaces'

const report: FileNode = { name: 'report.txt', path: 'attachments/docs/report.txt', type: 'file' }
const notes: FileNode = { name: 'notes.txt', path: 'attachments/notes.txt', type: 'file' }
const tree: FileNode[] = [
  { name: 'docs', type: 'folder', children: [report] },
  { name: 'images', type: 'folder', children: [] },
  notes,
]

function selectedNames(selected: FileNode | null): string[] {
  const wrapper = mount(FileTree, { props: { tree, selected } })
  const names = wrapper.findAll('.node.selected').map((row) => row.text())
  wrapper.unmount()
  return names
}

describe('FileTree selection', () => {
  it('marks no row as selected when nothing is selected', () => {
    expect(selectedNames(null)).toEqual([])
  })

  it('marks only the selected file', () => {
    expect(selectedNames(notes)).toEqual(['notes.txt'])
  })

  it('never matches path-less folders to a selected node without a path', () => {
    expect(selectedNames({ name: 'orphan.txt', type: 'file' })).toEqual([])
  })
})
