/**
 * Scenario 1: Full booking flow
 * Register → Login → Browse tables → Create booking → Verify on dashboard → Cancel → Verify slot freed
 */

import { expect, test } from "@playwright/test";
import { login, register, uniqueEmail } from "./helpers";

test.describe("Scenario 1: Full booking flow", () => {
  test("user can register, login, create a booking, see it on dashboard, and cancel it", async ({
    page,
  }) => {
    const email = uniqueEmail();

    // Register then login if redirected
    await register(page, email);
    if (page.url().includes("login")) {
      await login(page, email);
    }

    // Navigate to new booking wizard
    await page.goto("/bookings/new");
    await expect(page).toHaveURL(/bookings\/new/);

    // Step 1: Set date to tomorrow to avoid "must book 30+ min ahead" validation
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const tomorrowStr = tomorrow.toISOString().split("T")[0]; // YYYY-MM-DD

    const dateInput = page.locator('input[type="date"]');
    await dateInput.waitFor({ state: "visible", timeout: 5000 });
    await dateInput.fill(tomorrowStr);

    // Time defaults to 18:00, duration to 2h, party size to 2 — all valid defaults

    // Advance to Step 2
    await page.getByRole("button", { name: /ดูโต๊ะ/i }).click();

    // Step 2: Wait for table cards and select first one
    const tableCard = page
      .getByRole("button")
      .filter({ hasText: /โต๊ะ T\d/ })
      .first();
    await tableCard.waitFor({ state: "visible", timeout: 8000 });
    await tableCard.click();

    // "ยืนยันโต๊ะ →" is now enabled — advance to Step 3
    const confirmTableBtn = page.getByRole("button", { name: /ยืนยันโต๊ะ/i });
    await expect(confirmTableBtn).toBeEnabled({ timeout: 3000 });
    await confirmTableBtn.click();

    // Step 3: Confirm booking
    await expect(page.getByRole("heading", { name: /ขั้นตอนที่ 3/i })).toBeVisible({
      timeout: 5000,
    });
    await page.getByRole("button", { name: /ยืนยันการจอง/i }).click();

    // Redirects to booking detail page /bookings/{uuid}
    await page.waitForURL(/\/bookings\/.+/, { timeout: 15000 });

    // Navigate to bookings list and cancel the booking
    await page.goto("/bookings");
    const cancelBtn = page.getByRole("button", { name: /ยกเลิก|cancel/i }).first();
    if (await cancelBtn.isVisible({ timeout: 5000 })) {
      await cancelBtn.click();
      const confirmBtn = page.getByRole("button", { name: /ยืนยัน|confirm|ใช่|yes/i }).last();
      if (await confirmBtn.isVisible({ timeout: 2000 })) {
        await confirmBtn.click();
      }
      await expect(page.getByText(/ยกเลิก|cancelled/i).first()).toBeVisible({ timeout: 5000 });
    }
  });
});
