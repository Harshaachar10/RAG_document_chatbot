import { expect, test } from '@playwright/test';

test.describe('Doctor Intelligence demo journey', () => {
  test('search Sarah, open profile, and navigate evidence', async ({ page }) => {
    await page.goto('/golden-records');
    await expect(page.getByRole('heading', { name: 'Golden Doctor Records' })).toBeVisible();

    await page.getByPlaceholder('Name, alias, or HCP ID').fill('Sarah Lee');
    await expect(page.getByText('Sarah Lee-Kim').first()).toBeVisible({ timeout: 15000 });
    await page.getByText('Sarah Lee-Kim').first().click();
    await expect(page.getByText('HCP-000123')).toBeVisible();
    await expect(page.getByText('NPI: Not verified')).toBeVisible();

    await page.getByRole('tab', { name: 'Linked Records' }).click();
    await expect(page.getByText(/REC-/).first()).toBeVisible();

    await page.getByRole('tab', { name: 'History & Timeline' }).click();
    await expect(page.getByText(/Source record observed|Name change|Review decision/).first()).toBeVisible();
  });

  test('overview loads KPI cards from API', async ({ page }) => {
    await page.goto('/overview');
    await expect(page.getByRole('heading', { name: 'Doctor Identity Overview' })).toBeVisible();
    await expect(page.getByText('Golden Doctor Profiles')).toBeVisible({ timeout: 15000 });
    await expect(page.getByText('Synthetic data')).toBeVisible();
  });
});
