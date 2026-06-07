"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { useAdminBookings, type AdminBookingItem } from "@/lib/use-admin-bookings";

const STATUS_OPTIONS = [
  { value: "", label: "ทุกสถานะ" },
  { value: "confirmed", label: "ยืนยันแล้ว" },
  { value: "cancelled", label: "ยกเลิกแล้ว" },
  { value: "completed", label: "เสร็จสิ้น" },
  { value: "no_show", label: "ไม่มาตามนัด" },
];

const STATUS_BADGE: Record<string, string> = {
  confirmed: "bg-green-100 text-green-800",
  cancelled: "bg-red-100 text-red-800",
  completed: "bg-blue-100 text-blue-800",
  no_show: "bg-gray-100 text-gray-700",
};

const STATUS_LABEL: Record<string, string> = {
  confirmed: "ยืนยันแล้ว",
  cancelled: "ยกเลิกแล้ว",
  completed: "เสร็จสิ้น",
  no_show: "ไม่มาตามนัด",
};

function formatDateTime(iso: string) {
  return new Date(iso).toLocaleString("th-TH", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function AdminBookingsPage() {
  const { user } = useAuth();

  const [status, setStatus] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [page, setPage] = useState(1);

  const { data, isLoading, isError } = useAdminBookings({
    status: status || undefined,
    from_date: fromDate || undefined,
    to_date: toDate || undefined,
    page,
    limit: 20,
  });

  if (user?.role !== "staff" && user?.role !== "admin") {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center text-red-700">
        ไม่มีสิทธิ์เข้าถึงหน้านี้
      </div>
    );
  }

  const handleFilterReset = () => {
    setStatus("");
    setFromDate("");
    setToDate("");
    setPage(1);
  };

  const handleFilterChange = () => {
    setPage(1);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">จัดการการจองทั้งหมด</h1>
        <p className="mt-1 text-sm text-gray-500">ดูและกรองรายการจองจากผู้ใช้ทุกคน</p>
      </div>

      {/* Filter bar */}
      <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-end gap-4">
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-gray-600">สถานะ</label>
            <select
              value={status}
              onChange={(e) => { setStatus(e.target.value); handleFilterChange(); }}
              className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              {STATUS_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-gray-600">ตั้งแต่วันที่</label>
            <input
              type="date"
              value={fromDate}
              onChange={(e) => { setFromDate(e.target.value); handleFilterChange(); }}
              className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-gray-600">ถึงวันที่</label>
            <input
              type="date"
              value={toDate}
              onChange={(e) => { setToDate(e.target.value); handleFilterChange(); }}
              className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>

          <button
            onClick={handleFilterReset}
            className="rounded-lg border border-gray-300 px-4 py-2 text-sm text-gray-600 hover:bg-gray-50"
          >
            ล้างตัวกรอง
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-600 border-t-transparent" />
          </div>
        ) : isError ? (
          <div className="py-12 text-center text-red-600">เกิดข้อผิดพลาด กรุณาลองใหม่</div>
        ) : !data || data.data.length === 0 ? (
          <div className="py-12 text-center text-gray-500">ไม่พบรายการจอง</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-gray-200 bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">ผู้จอง</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">โต๊ะ</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">จำนวนคน</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">เริ่มต้น</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">สิ้นสุด</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">สถานะ</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">หมายเหตุ</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {data.data.map((booking: AdminBookingItem) => (
                  <tr key={booking.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <div className="font-medium text-gray-900">{booking.user_full_name}</div>
                      <div className="text-xs text-gray-500">{booking.user_email}</div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="font-medium text-gray-900">{booking.table.table_number}</div>
                      <div className="text-xs text-gray-500">{booking.table.location ?? "—"}</div>
                    </td>
                    <td className="px-4 py-3 text-gray-700">{booking.party_size} คน</td>
                    <td className="px-4 py-3 text-gray-700 whitespace-nowrap">{formatDateTime(booking.start_time)}</td>
                    <td className="px-4 py-3 text-gray-700 whitespace-nowrap">{formatDateTime(booking.end_time)}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_BADGE[booking.status] ?? "bg-gray-100 text-gray-700"}`}
                      >
                        {STATUS_LABEL[booking.status] ?? booking.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-500 max-w-[160px] truncate">
                      {booking.special_requests ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Pagination */}
      {data && data.meta.total_pages > 1 && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-500">
            รายการทั้งหมด {data.meta.total} รายการ (หน้า {data.meta.page}/{data.meta.total_pages})
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="rounded-lg border border-gray-300 px-3 py-1.5 disabled:opacity-40 hover:bg-gray-50"
            >
              ← ก่อนหน้า
            </button>
            <button
              onClick={() => setPage((p) => Math.min(data.meta.total_pages, p + 1))}
              disabled={page === data.meta.total_pages}
              className="rounded-lg border border-gray-300 px-3 py-1.5 disabled:opacity-40 hover:bg-gray-50"
            >
              ถัดไป →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
