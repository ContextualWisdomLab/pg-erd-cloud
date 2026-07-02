import { expect, test } from '@playwright/test';

const editorBaselines = [
  {
    name: 'desktop',
    screenshotName: 'demo-editor.png',
    viewport: { width: 1280, height: 720 },
  },
  {
    name: 'mobile review',
    screenshotName: 'demo-editor-mobile.png',
    viewport: { width: 390, height: 844 },
  },
] as const;

for (const baseline of editorBaselines) {
  test(`demo editor visual baseline remains stable on ${baseline.name}`, async ({ page }) => {
    await page.setViewportSize(baseline.viewport);
    await page.goto('/');

    await expect(page.getByRole('heading', { name: '대시보드' })).toBeVisible();
    await page
      .getByRole('navigation', { name: '주요 화면' })
      .getByRole('button', { name: '편집기', exact: true })
      .click();

    await expect(page.getByRole('toolbar', { name: 'ERD 캔버스 도구' })).toBeVisible();
    await expect(page.getByRole('searchbox', { name: '테이블 또는 컬럼 검색' })).toBeVisible();
    await expect(page.getByRole('button', { name: '공유 및 내보내기' })).toBeVisible();

    await expect(page).toHaveScreenshot(baseline.screenshotName, {
      animations: 'disabled',
      fullPage: false,
      maxDiffPixelRatio: 0.03,
    });
  });
}
