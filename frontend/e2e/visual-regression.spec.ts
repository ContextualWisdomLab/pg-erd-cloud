import { expect, test, type Page } from '@playwright/test';

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

async function openDemoEditor(page: Page, viewport: { width: number; height: number }) {
  await page.setViewportSize(viewport);
  await page.goto('/');

  await expect(page.getByRole('heading', { name: '대시보드' })).toBeVisible();
  await page
    .getByRole('navigation', { name: '주요 화면' })
    .getByRole('button', { name: '편집기', exact: true })
    .click();

  await expect(page.getByRole('toolbar', { name: 'ERD 캔버스 도구' })).toBeVisible();
  await expect(page.getByRole('searchbox', { name: '테이블 또는 컬럼 검색' })).toBeVisible();
  await expect(page.getByRole('button', { name: '공유 및 내보내기' })).toBeVisible();
}

async function openEmptyFirstRunDashboard(page: Page) {
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto('/?demo-workspace=empty');

  await expect(page.getByRole('heading', { name: '대시보드' })).toBeVisible();
  await expect(page.getByRole('navigation', { name: '주요 화면' })).toBeVisible();
  await expect(page.getByLabel('작업 요약')).toBeVisible();
  await expect(page.getByText('아직 프로젝트가 없습니다. 편집기에서 프로젝트를 생성하세요.')).toBeVisible();
  await expect(page.getByText('아직 다이어그램 스냅샷이 없습니다. 편집기에서 데이터베이스를 역공학해 시작하세요.')).toBeVisible();
}

for (const baseline of editorBaselines) {
  test(`demo editor visual baseline remains stable on ${baseline.name}`, async ({ page }) => {
    await openDemoEditor(page, baseline.viewport);

    await expect(page).toHaveScreenshot(baseline.screenshotName, {
      animations: 'disabled',
      fullPage: false,
      maxDiffPixelRatio: 0.03,
    });
  });
}

test('first-run empty dashboard visual baseline remains stable on desktop', async ({ page }) => {
  await openEmptyFirstRunDashboard(page);

  await expect(page).toHaveScreenshot('first-run-dashboard.png', {
    animations: 'disabled',
    fullPage: false,
    maxDiffPixelRatio: 0.03,
  });
});

test('share export modal visual baseline remains stable on desktop', async ({ page }) => {
  await openDemoEditor(page, { width: 1280, height: 720 });

  await page.getByRole('button', { name: '공유 및 내보내기' }).click();
  const dialog = page.getByRole('dialog', { name: '공유 및 내보내기' });

  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole('heading', { name: '공유 링크' })).toBeVisible();
  await expect(dialog.getByRole('heading', { name: '내보내기 산출물' })).toBeVisible();
  await expect(dialog.getByRole('button', { name: '링크 만들기' })).toBeVisible();

  await expect(dialog).toHaveScreenshot('share-export-modal.png', {
    animations: 'disabled',
    maxDiffPixelRatio: 0.06,
  });
});
