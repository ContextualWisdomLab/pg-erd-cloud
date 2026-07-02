import { expect, test } from '@playwright/test';

test('demo workspace loads, editor responds, and a screenshot is renderable', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('heading', { name: '대시보드' })).toBeVisible();
  await expect(page.getByRole('navigation', { name: '주요 화면' })).toBeVisible();

  await page
    .getByRole('navigation', { name: '주요 화면' })
    .getByRole('button', { name: '편집기', exact: true })
    .click();

  await expect(page.getByRole('toolbar', { name: 'ERD 캔버스 도구' })).toBeVisible();
  await expect(page.getByRole('button', { name: '공유 및 내보내기' })).toBeVisible();
  await expect(page.getByRole('searchbox', { name: '테이블 또는 컬럼 검색' })).toBeVisible();

  const screenshot = await page.screenshot({ fullPage: false });
  expect(screenshot.byteLength).toBeGreaterThan(10_000);
});

test('demo support operator can inspect billing diagnostics', async ({ page }) => {
  await page.goto('/?demo-support=operator');

  const navigation = page.getByRole('navigation', { name: '주요 화면' });
  await expect(navigation.getByRole('button', { name: '지원' })).toBeVisible();
  await navigation.getByRole('button', { name: '지원' }).click();

  await expect(page.getByRole('heading', { name: '지원 진단' })).toBeVisible();
  await page.getByRole('textbox', { name: '지원 진단 대상 subject' }).fill('customer-owner');
  await page.getByRole('button', { name: '조회' }).click();

  await expect(page.getByText('demo-customer-user', { exact: true })).toBeVisible();
  await expect(page.getByText('서명 토큰')).toBeVisible();
  await expect(page.getByRole('link', { name: '지원센터 열기' })).toHaveAttribute(
    'href',
    'https://support.example.com/billing',
  );
  await expect(page.getByRole('link', { name: '결제 포털 열기' })).toHaveAttribute(
    'href',
    'https://billing.example.com/customer/demo-customer-user',
  );
  await expect(page.getByRole('table', { name: '최근 공유 링크' })).toBeVisible();
  await expect(page.getByText('demo-share-active-1')).toBeVisible();
  await expect(page.getByRole('table', { name: '최근 결제 이벤트' })).toBeVisible();
  await expect(page.getByText('subscription.updated')).toBeVisible();
});
