import type { Locator, Page } from '@playwright/test'

export class WorkspacePage {
  readonly dashboardHeading: Locator
  readonly editorButton: Locator
  readonly projectSelect: Locator
  readonly connectionSelect: Locator
  readonly snapshotStatus: Locator

  constructor(private readonly page: Page) {
    this.dashboardHeading = page.getByRole('heading', { name: '대시보드' })
    this.editorButton = page.getByRole('button', { name: '편집기', exact: true })
    this.projectSelect = page.getByLabel('Project', { exact: true })
    this.connectionSelect = page.getByLabel('Connection', { exact: true })
    this.snapshotStatus = page.getByText(/^Snapshot: /)
  }

  async goto(): Promise<void> {
    await this.page.goto('/')
    await this.dashboardHeading.waitFor()
  }

  async openEditor(): Promise<void> {
    await this.editorButton.click()
  }

  async createProject(name: string): Promise<void> {
    await this.page.getByLabel('New project').fill(name)
    await this.page.getByRole('button', { name: 'Create', exact: true }).click()
    await this.projectSelect.selectOption({ label: name })
  }

  async createConnection(name: string, dsn: string): Promise<void> {
    await this.page.getByLabel('New connection (DSN)').fill(name)
    await this.page.getByRole('textbox', { name: 'Connection DSN' }).fill(dsn)
    await this.page.getByRole('button', { name: 'Save connection' }).click()
    await this.connectionSelect.selectOption({ label: name })
  }

  async reverseEngineer(schema: string): Promise<void> {
    await this.page.getByLabel('Schema filter (optional)').fill(schema)
    const button = this.page.getByRole('button', { name: /Reverse engineer/ })
    await button.click()
  }

  table(name: string): Locator {
    return this.page.getByRole('region', { name: `${name} 테이블` })
  }

  relation(name: string): Locator {
    return this.page.getByText(name, { exact: false })
  }
}
