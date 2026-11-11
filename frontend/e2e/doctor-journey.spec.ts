import { expect, test } from '@playwright/test';

test('dashboard, review, doctor, and how it works', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
  await expect(page.getByText('Synthetic data').first()).toBeVisible();
  await page.screenshot({ path: 'e2e/screenshots/dashboard-before.png', fullPage: true });

  await page.getByRole('button', { name: 'Run historical cleanup' }).click();
  await expect(page.getByRole('heading', { name: 'Running historical cleanup' })).toBeVisible();
  await page.screenshot({ path: 'e2e/screenshots/processing.png' });
  await expect(page.getByRole('button', { name: 'View dashboard' })).toBeVisible({ timeout: 90_000 });
  await page.getByRole('button', { name: 'View dashboard' }).click();
  await page.screenshot({ path: 'e2e/screenshots/dashboard-after.png', fullPage: true });

  await page.getByRole('button', { name: 'How it works' }).click();
  await expect(page.getByRole('heading', { name: 'How it works' })).toBeVisible();
  for (const [tab, file] of [
    ['Privacy', 'privacy'],
    ['Source profiles', 'source-profiles'],
    ['Cleanup runs', 'cleanup-runs'],
    ['Search quality', 'search-quality'],
    ['Accuracy scorecard', 'scorecard'],
    ['Audit log', 'audit'],
  ] as const) {
    await page.getByRole('tab', { name: tab }).click();
    await page.screenshot({ path: `e2e/screenshots/${file}.png` });
  }
  await page.getByRole('button', { name: 'Close drawer' }).click();

  await page.getByRole('link', { name: 'Review' }).click();
  await expect(page.getByRole('heading', { name: 'Review' })).toBeVisible();
  await page.screenshot({ path: 'e2e/screenshots/review.png', fullPage: true });

  await page.getByRole('link', { name: 'Golden Records' }).click();
  await expect(page.getByRole('heading', { name: 'Golden Records' })).toBeVisible();
  await page.getByLabel('Filter doctors').fill('Sarah Lee-Kim');
  await page.getByText('Sarah Lee-Kim', { exact: false }).first().click();
  await page.getByRole('tab', { name: 'Timeline' }).click();
  await page.screenshot({ path: 'e2e/screenshots/timeline.png' });
  await page.getByRole('tab', { name: 'Lineage' }).click();
  await expect(page.getByLabel('Lineage graph')).toBeVisible();
  await page.screenshot({ path: 'e2e/screenshots/lineage.png' });
  await page.getByRole('tab', { name: 'Prescriber impact' }).click();
  await page.screenshot({ path: 'e2e/screenshots/prescriber-impact.png' });
  await page.getByRole('tab', { name: 'Kept separate' }).click();
  await page.screenshot({ path: 'e2e/screenshots/kept-separate.png' });
  await page.getByRole('tab', { name: 'History' }).click();
  await page.screenshot({ path: 'e2e/screenshots/history.png' });
  await page.getByRole('button', { name: 'Ask' }).click();
  await page.getByRole('button', { name: 'Why are the two Sarah Lees separate?' }).click();
  await expect(page.getByText(/separate|stored/i).first()).toBeVisible();
  await page.screenshot({ path: 'e2e/screenshots/ask.png' });
});
