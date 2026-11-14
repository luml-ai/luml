import { describe, expect, it } from 'vitest'
import { escapeChartLabel, truncateChartLabel } from './charts'

describe('truncateChartLabel', () => {
  it.each([
    ['', ''],
    ['north – 東京', 'north – 東京'],
    ['abcdefghijklmnop', 'abcdefghijklmnop'],
    ['abcdefghijklmnopq', 'abcdefghijklmno…'],
    ['😀'.repeat(17), '😀'.repeat(15) + '…'],
  ])('shortens %j to at most 16 characters', (value, expected) => {
    expect(truncateChartLabel(value)).toBe(expected)
  })

  it('shortens multikilobyte labels', () => {
    expect(truncateChartLabel('x'.repeat(8192))).toBe('xxxxxxxxxxxxxxx…')
  })
})

describe('escapeChartLabel', () => {
  it.each([
    ['', ''],
    ['north – 東京', 'north – 東京'],
    ['<img src=x onerror="alert(1)">', '&lt;img src=x onerror=&quot;alert(1)&quot;&gt;'],
    ["Tom & 'Jerry'", 'Tom &amp; &#39;Jerry&#39;'],
    ['&lt;script&gt;', '&amp;lt;script&amp;gt;'],
  ])('escapes %j as text for chart HTML', (value, expected) => {
    expect(escapeChartLabel(value)).toBe(expected)
    const element = document.createElement('div')
    element.innerHTML = escapeChartLabel(value)
    expect(element.textContent).toBe(value)
    expect(element.childElementCount).toBe(0)
  })
})
