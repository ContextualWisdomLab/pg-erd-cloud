import type { ComponentProps } from 'react'
import type { Meta, StoryObj } from '@storybook/react-vite'
import { ExportModal } from './ExportModal'

const noop = () => undefined

export const exportModalStoryArgs = {
  isOpen: true,
  isCopied: false,
  hasDdlExport: false,
  hasDictionaryExport: false,
  hasDiagramExport: false,
  shareLinkUrl: '',
  isCreatingShareLink: false,
  isShareLinkCopied: false,
  shareLinkError: null,
  canCreateShareLink: false,
  onCloseExport: noop,
  onCopyExportDdl: noop,
  onDownloadSvg: noop,
  onDownloadUml: noop,
  onDownloadMermaid: noop,
  onExportDictionaryCsv: noop,
  onExportDictionaryMarkdown: noop,
  onDownloadDbml: noop,
  onDownloadPrisma: noop,
  onCreateShareLink: noop,
  onCopyShareLink: noop,
} satisfies ComponentProps<typeof ExportModal>

export const creatingShareLinkStoryArgs = {
  ...exportModalStoryArgs,
  canCreateShareLink: true,
  isCreatingShareLink: true,
}

export const readyExportStoryArgs = {
  ...exportModalStoryArgs,
  canCreateShareLink: true,
  hasDdlExport: true,
  hasDictionaryExport: true,
  hasDiagramExport: true,
}

export const errorExportStoryArgs = {
  ...exportModalStoryArgs,
  canCreateShareLink: true,
  shareLinkError: '공유 링크를 만들지 못했습니다. 잠시 후 다시 시도하세요.',
}

const meta = {
  title: 'Product/Share and Export/Export Modal',
  component: ExportModal,
  includeStories: /^[A-Z]/,
  parameters: {
    layout: 'fullscreen',
  },
  args: exportModalStoryArgs,
} satisfies Meta<typeof ExportModal>

export default meta
type Story = StoryObj<typeof meta>

export const PrerequisitesMissing: Story = {}

export const CreatingShareLink: Story = {
  args: creatingShareLinkStoryArgs,
}

export const Ready: Story = {
  args: readyExportStoryArgs,
}

export const ShareCreated: Story = {
  args: {
    ...readyExportStoryArgs,
    shareLinkUrl: 'https://example.test/share/demo',
  },
}

export const ErrorState: Story = {
  args: errorExportStoryArgs,
}

export const NarrowPrerequisitesMissing: Story = {
  parameters: {
    viewport: {
      defaultViewport: 'mobile1',
    },
  },
}
