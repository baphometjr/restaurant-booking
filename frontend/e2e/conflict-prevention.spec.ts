/**
 * Scenario 4: Conflict prevention
 * User A books a table → User B tries to book same table/time → sees unavailable feedback
 */

import { expect, test } from "@playwright/test";
import { uniqueEmail } from "./helpers";

const API = process.env.API_URL || "http://localhost:8000";

async function apiRegister(email: string): Promise<void> {
  await fetch(`${API}/api/v1/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password: "SecurePass1!", full_name: "E2E User" }),
  });
}

async function apiLogin(email: string): Promise<string> {
  const resp = await fetch(`${API}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password: "SecurePass1!" }),
  });
  const json = (await resp.json()) as { data: { access_token: string } };
  return json.data.access_token;
}

async function apiGetFirstAvailableTable(
  token: string,
  startIso: string,
  endIso: string
): Promise<string | null> {
  const params = new URLSearchParams({ start_time: startIso, end_time: endIso, party_size: "2" });
  const resp = await fetch(`${API}/api/v1/tables/available?${params}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const json = (await resp.json()) as { data: Array<{ id: string }> };
  return json.data[0]?.id ?? null;
}

async function apiCreateBooking(
  token: string,
  tableId: string,
  startIso: string,
  endIso: string
): Promise<{ status: number; body: unknown }> {
  const resp = await fetch(`${API}/api/v1/bookings`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ table_id: tableId, party_size: 2, start_time: startIso, end_time: endIso }),
  });
  return { status: resp.status, body: await resp.json() };
}

test.describe("Scenario 4: Conflict prevention", () => {
  test("second booking on the same table/time is rejected with conflict error", async () => {
    const emailA = uniqueEmail();
    const emailB = uniqueEmail();

    await apiRegister(emailA);
    await apiRegister(emailB);

    const tokenA = await apiLogin(emailA);
    const tokenB = await apiLogin(emailB);

    const start = new Date();
    start.setDate(start.getDate() + 2 + Math.floor(Math.random() * 5));
    start.setHours(14, 0, 0, 0);
    // Use relative offset (2h) instead of absolute hour to stay within 4h max duration
    const end = new Date(start.getTime() + 2 * 60 * 60 * 1000);

    // Get a table that is actually available at the chosen time to avoid cross-run collisions
    const tableId = await apiGetFirstAvailableTable(tokenA, start.toISOString(), end.toISOString());
    if (!tableId) {
      test.skip();
      return;
    }

    // User A books successfully
    const resultA = await apiCreateBooking(tokenA, tableId, start.toISOString(), end.toISOString());
    expect(resultA.status).toBe(201);

    // User B tries the same table/time → should get 409
    const resultB = await apiCreateBooking(tokenB, tableId, start.toISOString(), end.toISOString());
    expect(resultB.status).toBe(409);
    const bodyB = resultB.body as { error: { code: string } };
    expect(bodyB.error.code).toBe("TABLE_UNAVAILABLE");
  });
});
