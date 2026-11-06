import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'

function composite(foreground: string, background = '#ffffff'): number[] {
  const channels = (foreground.match(/[\da-f]{2}/gi) ?? []).map((channel) => parseInt(channel, 16))
  const alpha = (channels[3] ?? 255) / 255
  const backdrop = (background.match(/[\da-f]{2}/gi) ?? []).map((channel) => parseInt(channel, 16))
  return channels
    .slice(0, 3)
    .map((channel, index) => channel * alpha + backdrop[index] * (1 - alpha))
}

function luminance(channels: number[]): number {
  const linear = channels.map((channel) => {
    const value = channel / 255
    return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
  })
  return linear[0] * 0.2126 + linear[1] * 0.7152 + linear[2] * 0.0722
}

function contrast(foreground: string, background: string, backdrop?: string): number {
  const backgroundChannels = composite(background, backdrop)
  const foregroundChannels = composite(foreground)
  const values = [luminance(foregroundChannels), luminance(backgroundChannels)]
  return (Math.max(...values) + 0.05) / (Math.min(...values) + 0.05)
}

describe.each(['light', 'dark'])('%s theme text contrast', (name) => {
  const css = readFileSync(`src/assets/theme/${name}-theme.css`, 'utf8')
  const tokens = Object.fromEntries(
    [...css.matchAll(/--p-([\w-]+):\s*(#[\da-f]+);/gi)].map((match) => [match[1], match[2]]),
  )

  it.each(['', 'hover-', 'active-'])('keeps primary labels readable in the %s state', (state) => {
    expect(
      contrast(tokens['primary-contrast-color'], tokens[`primary-${state}color`]),
    ).toBeGreaterThanOrEqual(4.5)
  })

  it('keeps links readable on content and overlay backgrounds', () => {
    for (const background of ['content-background', 'overlay-modal-background']) {
      expect(contrast(tokens['text-link-color'], tokens[background])).toBeGreaterThanOrEqual(4.5)
    }
  })

  describe.each(['primary', 'danger', 'success', 'warn', 'info'])('%s buttons', (severity) => {
    it.each(['', 'hover-', 'active-'])('keeps labels readable in the %s state', (state) => {
      expect(
        contrast(
          tokens[`button-${severity}-${state}color`],
          tokens[`button-${severity}-${state}background`],
        ),
      ).toBeGreaterThanOrEqual(4.5)
    })
  })

  it('keeps outlined warning labels readable on dialog and interaction backgrounds', () => {
    for (const background of [
      'overlay-modal-background',
      'button-outlined-warn-hover-background',
      'button-outlined-warn-active-background',
    ]) {
      expect(
        contrast(
          tokens['button-outlined-warn-color'],
          tokens[background],
          tokens['overlay-modal-background'],
        ),
      ).toBeGreaterThanOrEqual(4.5)
    }
  })

  describe.each(['message', 'toast'])('%s notifications', (component) => {
    it.each(['success', 'warn', 'error', 'info'])(
      'keeps %s text readable over its translucent fill',
      (severity) => {
        expect(
          contrast(
            tokens[`${component}-${severity}-color`],
            tokens[`${component}-${severity}-background`],
            tokens['content-background'],
          ),
        ).toBeGreaterThanOrEqual(4.5)
      },
    )
  })
})
