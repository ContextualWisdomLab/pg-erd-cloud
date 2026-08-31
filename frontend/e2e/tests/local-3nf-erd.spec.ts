import { expect, test } from '@playwright/test'
import { WorkspacePage } from '../pages/workspace.page'

const apiKey = process.env.E2E_API_KEY
const targetDsn = process.env.E2E_TARGET_DSN

test.beforeEach(async ({ page }) => {
  if (!apiKey) throw new Error('E2E_API_KEY is required')

  await page.context().setExtraHTTPHeaders({ authorization: `Bearer ${apiKey}` })
})

test('reverse engineers the local 3NF schema into the ERD canvas', async ({ page }) => {
  if (!targetDsn) throw new Error('E2E_TARGET_DSN is required')

  const projectName = `local-3nf-${Date.now()}`
  const workspace = new WorkspacePage(page)

  await workspace.goto()
  await expect(workspace.dashboardHeading).toBeVisible()
  await workspace.openEditor()

  await workspace.createProject(projectName)
  await expect(workspace.projectSelect).toContainText(projectName)

  await workspace.createConnection('local-3nf-target', targetDsn)
  await expect(workspace.connectionSelect).toContainText('local-3nf-target')

  await workspace.reverseEngineer('e2e_3nf')

  await expect(workspace.snapshotStatus).toHaveText('Snapshot: succeeded', { timeout: 90_000 })
  await expect(workspace.table('e2e_3nf.customer_account')).toBeVisible()
  await expect(workspace.table('e2e_3nf.product_catalog')).toBeVisible()
  await expect(workspace.table('e2e_3nf.sales_order')).toBeVisible()
  await expect(workspace.table('e2e_3nf.sales_order_line')).toBeVisible()

  await expect(workspace.relation('fk_sales_order_customer_account')).toBeVisible()
  await expect(workspace.relation('fk_sales_order_line_sales_order')).toBeVisible()
})
