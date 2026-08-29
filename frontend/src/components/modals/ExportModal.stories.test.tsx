import { readFileSync } from 'node:fs'
import React from 'react'
import { cleanup, render, screen } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import { afterEach, describe, expect, it } from 'vitest'
import { ExportModal } from './ExportModal'
import exportModalMeta, {
  creatingShareLinkStoryArgs,
  errorExportStoryArgs,
  exportModalStoryArgs,
  readyExportStoryArgs,
} from './ExportModal.stories'

afterEach(cleanup)

describe('ExportModal Storybook state contract', () => {
  it('indexes only UpperCamelCase Storybook exports', () => {
    const includeStories = exportModalMeta.includeStories
    expect(includeStories).toBeInstanceOf(RegExp)
    if (!(includeStories instanceof RegExp)) {
      throw new Error('includeStories must be a RegExp')
    }
    expect(includeStories.test('PrerequisitesMissing')).toBe(true)
    expect(includeStories.test('exportModalStoryArgs')).toBe(false)
  })

  it('keeps aria-disabled primary actions visually unavailable on hover', () => {
    const css = readFileSync(new URL('../../accessibility.css', import.meta.url), 'utf8')
    const selector = '.exportModal .exportModal__primaryAction[aria-disabled="true"]:hover'
    const start = css.indexOf(selector)
    expect(start).toBeGreaterThanOrEqual(0)
    const end = css.indexOf('}', start)
    expect(end).toBeGreaterThan(start)
    const block = css.slice(start, end)
    expect(block).toContain('background-color: var(--color-surface-muted)')
    expect(block).toContain('color: var(--color-disabled)')
  })

  it('keeps unavailable actions focusable and explains the next action', () => {
    render(<ExportModal {...exportModalStoryArgs} />)

    const createShareLink = screen.getByRole('button', { name: '링크 만들기' })
    expect(createShareLink).toHaveAttribute('aria-disabled', 'true')
    expect(createShareLink).not.toBeDisabled()
    expect(createShareLink).toHaveAttribute('aria-describedby', 'share-link-create-hint')
    expect(screen.getByText('먼저 프로젝트를 선택하세요.')).toBeVisible()
    expect(screen.getAllByText('먼저 테이블을 추가하세요')).toHaveLength(8)

    const unavailableActions = screen
      .getAllByRole('button')
      .filter((button) => button.getAttribute('aria-disabled') === 'true')
    expect(unavailableActions).toHaveLength(10)
  })

  it('uses native disabled only while share-link creation is actually in flight', () => {
    render(<ExportModal {...creatingShareLinkStoryArgs} />)

    const creating = screen.getByRole('button', { name: '생성 중...' })
    expect(creating).toBeDisabled()
    expect(creating).toHaveAttribute('aria-busy', 'true')
  })

  it('exposes ready actions without aria-disabled', () => {
    render(<ExportModal {...readyExportStoryArgs} />)

    expect(screen.getByRole('button', { name: '링크 만들기' })).not.toHaveAttribute('aria-disabled')
    expect(screen.getByRole('button', { name: 'SQL DDL 복사' })).not.toHaveAttribute('aria-disabled')
  })

  it('announces the retry-oriented error state as an alert', () => {
    render(<ExportModal {...errorExportStoryArgs} />)

    expect(screen.getByRole('alert')).toHaveTextContent(
      '공유 링크를 만들지 못했습니다. 잠시 후 다시 시도하세요.',
    )
  })
})
