"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useParams } from "next/navigation";
import { useBooking, useCancelBooking } from "@/lib/use-bookings";
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
  return new Date(iso).toLocaleString("th-TH", {
    dateStyle: "long",
    timeStyle: "short",
  });
}

function isEditable(booking: BookingResponse) {
  return (
    booking.status === "confirmed" &&
    new Date(booking.start_time) > new Date()
  );
}

export default function BookingDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { data: booking, isPending, error } = useBooking(id);
  const cancelMutation = useCancelBooking();
  const [showConfirm, setShowConfirm] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);

  if (isPending) {
    return (
      <div className="flex justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-600 border-t-transparent" />
      </div>
    );
  }

  if (error || !booking) {
    return (
      <div className="space-y-4">
        <Link href="/bookings" className="text-sm text-indigo-600 hover:underline">
          ← กลับไปรายการจอง
        </Link>
        <div className="rounded-xl bg-red-50 p-4 text-sm text-red-700">
          ไม่พบข้อมูลการจอง
        </div>
      </div>
    );
  }

  async function handleCancel() {
    setCancelError(null);
    try {
      await cancelMutation.mutateAsync(id);
      setShowConfirm(false);
      router.push("/bookings");
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "ยกเลิกไม่สำเร็จ กรุณาลองใหม่";
      setCancelError(msg);
    }
  }

  const editable = isEditable(booking);

  return (
    <div className="space-y-6">
      <Link href="/bookings" className="text-sm text-indigo-600 hover:underline">
        ← กลับไปรายการจอง
      </Link>

      <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
        <div className="flex items-start justify-between gap-4">
          <h1 className="text-xl font-bold text-gray-900">
            โต๊ะ {booking.table.table_number}
          </h1>
          <span
            className={`rounded-full px-3 py-1 text-sm font-medium ${STATUS_COLOR[booking.status]}`}
          >
            {STATUS_LABEL[booking.status]}
          </span>
        </div>

        <dl className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <dt className="text-sm font-medium text-gray-500">สถานที่</dt>
            <dd className="mt-1 text-gray-900">{booking.table.location ?? "-"}</dd>
          </div>
          <div>
            <dt className="text-sm font-medium text-gray-500">ความจุ</dt>
            <dd className="mt-1 text-gray-900">{booking.table.capacity} คน</dd>
          </div>
          <div>
            <dt className="text-sm font-medium text-gray-500">เริ่มต้น</dt>
            <dd className="mt-1 text-gray-900">{formatDateTime(booking.start_time)}</dd>
          </div>
          <div>
            <dt className="text-sm font-medium text-gray-500">สิ้นสุด</dt>
            <dd className="mt-1 text-gray-900">{formatDateTime(booking.end_time)}</dd>
          </div>
          <div>
            <dt className="text-sm font-medium text-gray-500">จำนวนคน</dt>
            <dd className="mt-1 text-gray-900">{booking.party_size} คน</dd>
          </div>
          <div>
            <dt className="text-sm font-medium text-gray-500">วันที่จอง</dt>
            <dd className="mt-1 text-gray-900">
              {new Date(booking.created_at).toLocaleDateString("th-TH", { dateStyle: "medium" })}
            </dd>
          </div>
        </dl>

        {booking.special_requests && (
          <div className="mt-5 rounded-xl bg-gray-50 p-4">
            <dt className="text-sm font-medium text-gray-500">คำขอพิเศษ</dt>
            <dd className="mt-1 text-gray-900">{booking.special_requests}</dd>
          </div>
        )}

        {editable && (
          <div className="mt-6 flex flex-wrap gap-3">
            <Link
              href={`/bookings/${id}/edit`}
              className="rounded-lg border border-indigo-600 px-4 py-2 text-sm font-medium text-indigo-600 hover:bg-indigo-50"
            >
              แก้ไขการจอง
            </Link>
            <button
              onClick={() => setShowConfirm(true)}
              className="rounded-lg border border-red-500 px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50"
            >
              ยกเลิกการจอง
            </button>
          </div>
        )}
      </div>

      {showConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-sm rounded-2xl bg-white p-6 shadow-xl">
            <h2 className="text-lg font-semibold text-gray-900">ยืนยันการยกเลิก</h2>
            <p className="mt-2 text-sm text-gray-600">
              คุณต้องการยกเลิกการจองโต๊ะ {booking.table.table_number} ใช่หรือไม่?
              การยกเลิกไม่สามารถเรียกคืนได้
            </p>
            {cancelError && (
              <p className="mt-3 text-sm text-red-600">{cancelError}</p>
            )}
            <div className="mt-5 flex gap-3">
              <button
                onClick={() => { setShowConfirm(false); setCancelError(null); }}
                className="flex-1 rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
                disabled={cancelMutation.isPending}
              >
                ไม่ใช่
              </button>
              <button
                onClick={handleCancel}
                disabled={cancelMutation.isPending}
                className="flex-1 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
              >
                {cancelMutation.isPending ? "กำลังยกเลิก..." : "ยืนยันยกเลิก"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
