import { fromCSV } from 'arquero'
import { describe, expect, it } from 'vitest'
import { convertObjectToCsvBlob } from './helpers'

const readBlob = (blob: Blob): Promise<string> =>
  new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result as string)
    reader.onerror = () => reject(reader.error)
    reader.readAsText(blob)
  })

describe('convertObjectToCsvBlob', () => {
  it('preserves generated values containing commas when parsed as CSV', async () => {
    const blob = convertObjectToCsvBlob({
      feature: ['first', 'second'],
      prediction: ['Yes, approved', 'No'],
    })

    expect(fromCSV(await readBlob(blob)).objects()).toEqual([
      { feature: 'first', prediction: 'Yes, approved' },
      { feature: 'second', prediction: 'No' },
    ])
  })

  it('escapes quotes and line breaks in headers and values', async () => {
    const blob = convertObjectToCsvBlob({ 'feature,name': ['He said "yes"\nthen left'] })

    expect(fromCSV(await readBlob(blob)).objects()).toEqual([
      { 'feature,name': 'He said "yes"\nthen left' },
    ])
  })

  it('keeps missing values in their columns', async () => {
    const blob = convertObjectToCsvBlob({ feature: ['first', 'second'], prediction: ['Yes'] })

    expect(fromCSV(await readBlob(blob)).objects()).toEqual([
      { feature: 'first', prediction: 'Yes' },
      { feature: 'second', prediction: null },
    ])
  })
})
