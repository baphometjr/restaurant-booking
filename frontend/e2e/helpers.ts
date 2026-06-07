import { Page } from "@playwright/test";

export function uniqueEmail(): string {
  return `e2e_${Date.now()}_${Math.random().toString(36).slice(2, 7)}@test.com`;
}

export async function register(
  page: Page,
  email: string,
  password = "SecurePass1!"
): Promise<void> {
  await page.goto("/register");
  await page.getByLabel(/อีเมล/i).fill(email);
  await page.getByLabel(/รหัสผ่าน/i).first().fill(password);
  await page.getByLabel(/ชื่อ/i).fill("E2E Tester");
  await page.getByRole("button", { name: /สมัคร|register/i }).click();
  await page.waitForURL(/dashboard|login/);
}

export async function login(
  page: Page,
  email: string,
  password = "SecurePass1!"
): Promise<void> {
  await page.goto("/login");
  await page.getByLabel(/อีเมล/i).fill(email);
  await page.getByLabel(/รหัสผ่าน/i).fill(password);
  await page.getByRole("button", { name: /เข้าสู่ระบบ|login/i }).click();
  await page.waitForURL(/dashboard/);
}
