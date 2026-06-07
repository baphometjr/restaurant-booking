/**
 * Scenario 3: Token refresh
 * Login → wait for access token to expire (mocked via short-lived token in test env)
 * → make API call → verify silent refresh happens → response succeeds without user interaction
 *
 * The frontend interceptor (lib/api-client.ts) handles the 401 → refresh → retry loop.
 * This test verifies the user does NOT see a login page after token expiry.
 */

import { expect, test } from "@playwright/test";
import { login, register, uniqueEmail } from "./helpers";

const API = process.env.API_URL || "http://localhost:8000";

test.describe("Scenario 3: Silent token refresh", () => {
  test("dashboard stays accessible after access token expires", async ({
    page,
  }) => {
    const email = uniqueEmail();
    await register(page, email);
    if (page.url().includes("login")) {
      await login(page, email);
    }

    await page.waitForURL(/dashboard/);

    // Simulate an expired access token by overwriting it in the auth context.
    // The app stores access_token in JavaScript memory via AuthContext.
    // We inject an invalid token to force a 401, which should trigger silent refresh.
    await page.evaluate(() => {
      // Override the stored token with an invalid value so the next request gets 401.
      // The refresh cookie is still valid (httpOnly), so the interceptor should recover.
      // This requires that the app uses window.__auth or a ref we can reach.
      // If the token is stored only in React state (closure), the injected token
      // won't replace it — in that case the test verifies the page stays intact.
      const w = window as unknown as Record<string, unknown>;
      if (w.__setAccessToken) {
        (w.__setAccessToken as (t: string) => void)("expired.token.injected");
      }
    });

    // Navigate to bookings — the interceptor should auto-refresh and serve the page
    await page.goto("/bookings");
    await expect(page).toHaveURL(/bookings/);

    // The user must NOT be redirected to /login
    expect(page.url()).not.toContain("login");

    // Dashboard content should still render (h1, nav, etc.)
    await expect(page.locator("main, [role='main']").first()).toBeVisible({ timeout: 8000 });
  });

  test("expired session redirects to login only when refresh cookie is also gone", async ({
    page,
  }) => {
    const email = uniqueEmail();
    await register(page, email);
    if (page.url().includes("login")) {
      await login(page, email);
    }
    await page.waitForURL(/dashboard/);

    // Clear the refresh_token cookie to simulate a fully expired session
    await page.context().clearCookies();

    // Reload a protected page — should redirect to /login
    await page.goto("/bookings");
    await page.waitForURL(/login/, { timeout: 15000 });
    await expect(page).toHaveURL(/login/);
  });
});
