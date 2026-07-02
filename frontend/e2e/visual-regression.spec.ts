import { expect, test } from '@playwright/test';

test('demo editor visual baseline remains stable', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('heading', { name: '대시보드' })).toBeVisible();
  await page
    .getByRole('navigation', { name: '주요 화면' })
    .getByRole('button', { name: '편집기', exact: true })
    .click();

  await expect(page.getByRole('toolbar', { name: 'ERD 캔버스 도구' })).toBeVisible();
  await expect(page.getByRole('searchbox', { name: '테이블 또는 컬럼 검색' })).toBeVisible();

  await expect(page).toHaveScreenshot('demo-editor.png', {
    animations: 'disabled',
    fullPage: false,
    maxDiffPixelRatio: 0.03,
  });
});
