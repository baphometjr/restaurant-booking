"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth-context";

export default function DashboardPage() {
  const { user } = useAuth();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">
          สวัสดี, {user?.full_name}
        </h1>
        <p className="mt-1 text-gray-500">จัดการการจองโต๊ะของคุณได้ที่นี่</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Link
          href="/bookings/new"
          className="flex flex-col gap-2 rounded-2xl bg-indigo-600 p-6 text-white shadow hover:bg-indigo-700"
        >
          <span className="text-3xl">🍽️</span>
          <span className="text-lg font-semibold">จองโต๊ะใหม่</span>
          <span className="text-sm text-indigo-200">เลือกโต๊ะ วันเวลา และจำนวนคน</span>
        </Link>

        <Link
          href="/bookings"
          className="flex flex-col gap-2 rounded-2xl bg-white p-6 shadow hover:shadow-md"
        >
          <span className="text-3xl">📋</span>
          <span className="text-lg font-semibold text-gray-900">การจองของฉัน</span>
          <span className="text-sm text-gray-500">ดู แก้ไข หรือยกเลิกการจอง</span>
        </Link>
      </div>
    </div>
  );
}
