"use client";

import Link from "next/link";
import { useMyBookings } from "@/lib/use-bookings";
import type { BookingResponse } from "@/lib/types";

const STATUS_LABEL: Record<BookingResponse["status"], string> = {
  confirmed: "ยืนยันแล้ว",
  cancelled: "ยกเลิกแล้ว",
  completed: "เสร็จสิ้น",
  no_show: "ไม่มาใช้บริการ",
};

const STATUS_COLOR: Record<BookingResponse["status"], string> = {
  confirmed: "bg-green-100 text-green-800",
  cancelled: "bg-red-100 text-red-800",
  completed: "bg-gray-100 text-gray-700",
  no_show: "bg-yellow-100 text-yellow-800",
};

function formatDateTime(iso: string) {
  const d = new Date(iso);
  return d.toLocaleString("th-TH", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function BookingCard({ booking }: { booking: BookingResponse }) {
  return (
    <Link
      href={`/bookings/${booking.id}`}
      className="block rounded-2xl border border-gray-200 bg-white p-5 shadow-sm hover:shadow-md transition-shadow"
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-lg font-semibold text-gray-900">
              โต๊ะ {booking.table.table_number}
            </span>
            {booking.table.location && (
              <span className="text-sm text-gray-500">({booking.table.location})</span>
            )}
          </div>
          <p className="mt-1 text-sm text-gray-600">
            {formatDateTime(booking.start_time)} — {new Date(booking.end_time).toLocaleTimeString("th-TH", { timeStyle: "short" })}
          </p>
          <p className="mt-1 text-sm text-gray-500">{booking.party_size} คน</p>
          {booking.special_requests && (
            <p className="mt-1 text-sm text-gray-400 italic">"{booking.special_requests}"</p>
          )}
        </div>
        <span
          className={`shrink-0 rounded-full px-3 py-1 text-xs font-medium ${STATUS_COLOR[booking.status]}`}
        >
          {STATUS_LABEL[booking.status]}
        </span>
      </div>
    </Link>
  );
}

export default function BookingsPage() {
  const { data: bookings, isPending, error } = useMyBookings();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">การจองของฉัน</h1>
        <Link
          href="/bookings/new"
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
        >
          + จองโต๊ะใหม่
        </Link>
      </div>

      {isPending && (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-600 border-t-transparent" />
        </div>
      )}

      {error && (
        <div className="rounded-xl bg-red-50 p-4 text-sm text-red-700">
          โหลดข้อมูลไม่สำเร็จ กรุณาลองใหม่อีกครั้ง
        </div>
      )}

      {bookings && bookings.length === 0 && (
        <div className="rounded-2xl border-2 border-dashed border-gray-200 py-16 text-center">
          <p className="text-3xl">🍽️</p>
          <p className="mt-3 text-gray-500">ยังไม่มีการจอง</p>
          <Link
            href="/bookings/new"
            className="mt-4 inline-block rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
          >
            จองโต๊ะเดี๋ยวนี้
          </Link>
        </div>
      )}

      {bookings && bookings.length > 0 && (
        <div className="space-y-3">
          {bookings.map((b) => (
            <BookingCard key={b.id} booking={b} />
          ))}
        </div>
      )}
    </div>
  );
}
