"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useAvailableTables } from "@/lib/use-tables";
import { useBooking, useEditBooking } from "@/lib/use-bookings";
import type { TableInfo } from "@/lib/types";

const DURATIONS = [
  { label: "1 ชั่วโมง", hours: 1 },
  { label: "1.5 ชั่วโมง", hours: 1.5 },
  { label: "2 ชั่วโมง", hours: 2 },
  { label: "2.5 ชั่วโมง", hours: 2.5 },
  { label: "3 ชั่วโมง", hours: 3 },
];

const TIME_SLOTS = Array.from({ length: 23 }, (_, i) => {
  const hour = 11 + Math.floor(i / 2);
  const min = i % 2 === 0 ? "00" : "30";
  return `${hour.toString().padStart(2, "0")}:${min}`;
}).filter((t) => t <= "21:30");

interface Step1Data {
  date: string;
  time: string;
  durationHours: number;
  partySize: number;
}

function buildIso(date: string, time: string): string {
  return new Date(`${date}T${time}:00`).toISOString();
}

function addHours(iso: string, hours: number): string {
  const d = new Date(iso);
  d.setTime(d.getTime() + hours * 60 * 60 * 1000);
  return d.toISOString();
}

function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString("th-TH", { timeStyle: "short" });
}

function localDate(iso: string) {
  const d = new Date(iso);
  const y = d.getFullYear();
  const m = (d.getMonth() + 1).toString().padStart(2, "0");
  const day = d.getDate().toString().padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function localTime(iso: string) {
  const d = new Date(iso);
  const h = d.getHours().toString().padStart(2, "0");
  const min = d.getMinutes().toString().padStart(2, "0");
  return `${h}:${min}`;
}

function calcDuration(startIso: string, endIso: string): number {
  return (new Date(endIso).getTime() - new Date(startIso).getTime()) / 3_600_000;
}

function Step1({
  initial,
  onNext,
  bookingId,
}: {
  initial: Step1Data;
  onNext: (d: Step1Data) => void;
  bookingId: string;
}) {
  const today = new Date().toISOString().split("T")[0];
  const [date, setDate] = useState(initial.date);
  const [time, setTime] = useState(initial.time);
  const [durationHours, setDuration] = useState(initial.durationHours);
  const [partySize, setPartySize] = useState(initial.partySize);
  const [err, setErr] = useState("");

  const handleNext = () => {
    if (!date || !time) {
      setErr("กรุณากรอกข้อมูลให้ครบถ้วน");
      return;
    }
    const start = new Date(`${date}T${time}:00`);
    const now = new Date();
    now.setMinutes(now.getMinutes() + 30);
    if (start <= now) {
      setErr("ต้องจองล่วงหน้าอย่างน้อย 30 นาที");
      return;
    }
    setErr("");
    onNext({ date, time, durationHours, partySize });
  };

  return (
    <div className="space-y-5">
      <h2 className="text-lg font-semibold text-gray-900">ขั้นตอนที่ 1 — เลือกวันและเวลาใหม่</h2>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="block text-sm font-medium text-gray-700">วันที่</label>
          <input
            type="date"
            min={today}
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700">เวลาเริ่มต้น</label>
          <select
            value={time}
            onChange={(e) => setTime(e.target.value)}
            className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          >
            {TIME_SLOTS.map((t) => (
              <option key={t} value={t}>{t} น.</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700">ระยะเวลา</label>
          <select
            value={durationHours}
            onChange={(e) => setDuration(Number(e.target.value))}
            className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          >
            {DURATIONS.map((d) => (
              <option key={d.hours} value={d.hours}>{d.label}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700">จำนวนคน</label>
          <select
            value={partySize}
            onChange={(e) => setPartySize(Number(e.target.value))}
            className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          >
            {Array.from({ length: 12 }, (_, i) => i + 1).map((n) => (
              <option key={n} value={n}>{n} คน</option>
            ))}
          </select>
        </div>
      </div>

      {err && <p className="text-sm text-red-600">{err}</p>}

      <div className="flex gap-3">
        <Link
          href={`/bookings/${bookingId}`}
          className="flex-1 rounded-lg border border-gray-300 py-2.5 text-center text-sm font-semibold text-gray-700 hover:bg-gray-50"
        >
          ← ยกเลิก
        </Link>
        <button
          onClick={handleNext}
          className="flex-1 rounded-lg bg-indigo-600 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700"
        >
          ดูโต๊ะที่ว่าง →
        </button>
      </div>
    </div>
  );
}

function Step2({
  step1,
  bookingId,
  currentTableId,
  onNext,
  onBack,
}: {
  step1: Step1Data;
  bookingId: string;
  currentTableId: string;
  onNext: (table: TableInfo) => void;
  onBack: () => void;
}) {
  const startIso = buildIso(step1.date, step1.time);
  const endIso = addHours(startIso, step1.durationHours);
  const [selected, setSelected] = useState<TableInfo | null>(null);

  const { data: tables, isPending, error } = useAvailableTables({
    start_time: startIso,
    end_time: endIso,
    party_size: step1.partySize,
    exclude_booking_id: bookingId,
  });

  return (
    <div className="space-y-5">
      <h2 className="text-lg font-semibold text-gray-900">ขั้นตอนที่ 2 — เลือกโต๊ะ</h2>

      <div className="rounded-xl bg-indigo-50 px-4 py-3 text-sm text-indigo-700">
        {new Date(step1.date).toLocaleDateString("th-TH", { dateStyle: "long" })}
        {" · "}
        {step1.time} — {formatTime(endIso)} น.
        {" · "}
        {step1.partySize} คน
      </div>

      {isPending && (
        <div className="flex justify-center py-8">
          <div className="h-7 w-7 animate-spin rounded-full border-4 border-indigo-600 border-t-transparent" />
        </div>
      )}

      {error && (
        <p className="text-sm text-red-600">โหลดโต๊ะไม่สำเร็จ กรุณาลองใหม่</p>
      )}

      {tables && tables.length === 0 && (
        <div className="rounded-xl bg-yellow-50 p-4 text-sm text-yellow-800">
          ไม่มีโต๊ะว่างสำหรับช่วงเวลานี้ กรุณาเลือกเวลาอื่น
        </div>
      )}

      {tables && tables.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {tables.map((t) => (
            <button
              key={t.id}
              onClick={() => setSelected(t)}
              className={`rounded-xl border-2 p-4 text-left transition-all ${
                selected?.id === t.id
                  ? "border-indigo-600 bg-indigo-50 shadow-md"
                  : t.id === currentTableId
                  ? "border-indigo-300 bg-indigo-50/50"
                  : "border-gray-200 bg-white hover:border-indigo-300"
              }`}
            >
              <div className="flex items-center gap-2">
                <span className="text-base font-bold text-gray-900">โต๊ะ {t.table_number}</span>
                {t.id === currentTableId && (
                  <span className="rounded-full bg-indigo-100 px-2 py-0.5 text-xs text-indigo-700">
                    โต๊ะปัจจุบัน
                  </span>
                )}
              </div>
              <div className="mt-1 text-sm text-gray-500">
                {t.capacity} คน
                {t.location && ` · ${t.location}`}
              </div>
            </button>
          ))}
        </div>
      )}

      <div className="flex gap-3">
        <button
          onClick={onBack}
          className="flex-1 rounded-lg border border-gray-300 py-2.5 text-sm font-semibold text-gray-700 hover:bg-gray-50"
        >
          ← ย้อนกลับ
        </button>
        <button
          disabled={!selected}
          onClick={() => selected && onNext(selected)}
          className="flex-1 rounded-lg bg-indigo-600 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-40"
        >
          ยืนยันโต๊ะ →
        </button>
      </div>
    </div>
  );
}

function Step3({
  step1,
  table,
  bookingId,
  initialSpecialRequests,
  onBack,
}: {
  step1: Step1Data;
  table: TableInfo;
  bookingId: string;
  initialSpecialRequests: string | null;
  onBack: () => void;
}) {
  const router = useRouter();
  const { mutateAsync, isPending } = useEditBooking(bookingId);
  const [specialRequests, setSpecialRequests] = useState(initialSpecialRequests ?? "");
  const [serverError, setServerError] = useState("");

  const startIso = buildIso(step1.date, step1.time);
  const endIso = addHours(startIso, step1.durationHours);

  const handleConfirm = async () => {
    setServerError("");
    try {
      await mutateAsync({
        table_id: table.id,
        start_time: startIso,
        end_time: endIso,
        party_size: step1.partySize,
        special_requests: specialRequests.trim() || null,
      });
      router.push(`/bookings/${bookingId}`);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: { message?: string } } } })
          ?.response?.data?.detail?.message ?? "เกิดข้อผิดพลาด กรุณาลองใหม่";
      setServerError(msg);
    }
  };

  return (
    <div className="space-y-5">
      <h2 className="text-lg font-semibold text-gray-900">ขั้นตอนที่ 3 — ยืนยันการแก้ไข</h2>

      <div className="divide-y divide-gray-100 rounded-2xl border border-gray-200 bg-white">
        <dl className="grid grid-cols-2 gap-x-4 gap-y-0 p-5">
          {[
            ["โต๊ะ", `${table.table_number}${table.location ? ` (${table.location})` : ""}`],
            ["ความจุ", `${table.capacity} คน`],
            ["วันที่", new Date(step1.date).toLocaleDateString("th-TH", { dateStyle: "long" })],
            ["เวลา", `${step1.time} — ${formatTime(endIso)} น.`],
            ["จำนวนคน", `${step1.partySize} คน`],
          ].map(([label, value]) => (
            <div key={label} className="py-3">
              <dt className="text-sm text-gray-500">{label}</dt>
              <dd className="mt-0.5 font-medium text-gray-900">{value}</dd>
            </div>
          ))}
        </dl>

        <div className="p-5">
          <label className="block text-sm font-medium text-gray-700">คำขอพิเศษ (ถ้ามี)</label>
          <textarea
            rows={3}
            value={specialRequests}
            onChange={(e) => setSpecialRequests(e.target.value)}
            placeholder="เช่น ที่นั่งริมหน้าต่าง, อาหารพิเศษ..."
            className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
        </div>
      </div>

      {serverError && (
        <p className="rounded-lg bg-red-50 px-4 py-2 text-sm text-red-700">{serverError}</p>
      )}

      <div className="flex gap-3">
        <button
          onClick={onBack}
          disabled={isPending}
          className="flex-1 rounded-lg border border-gray-300 py-2.5 text-sm font-semibold text-gray-700 hover:bg-gray-50 disabled:opacity-40"
        >
          ← ย้อนกลับ
        </button>
        <button
          onClick={handleConfirm}
          disabled={isPending}
          className="flex-1 rounded-lg bg-indigo-600 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-40"
        >
          {isPending ? "กำลังบันทึก..." : "บันทึกการแก้ไข ✓"}
        </button>
      </div>
    </div>
  );
}

type Step = 1 | 2 | 3;
const STEP_LABELS = ["เลือกวันเวลา", "เลือกโต๊ะ", "ยืนยัน"];

export default function EditBookingPage() {
  const { id } = useParams<{ id: string }>();
  const { data: booking, isPending: loadingBooking } = useBooking(id);

  const [step, setStep] = useState<Step>(1);
  const [step1Data, setStep1Data] = useState<Step1Data | null>(null);
  const [selectedTable, setSelectedTable] = useState<TableInfo | null>(null);

  if (loadingBooking) {
    return (
      <div className="flex justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-600 border-t-transparent" />
      </div>
    );
  }

  if (!booking) {
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

  const initialStep1: Step1Data = {
    date: localDate(booking.start_time),
    time: localTime(booking.start_time),
    durationHours: calcDuration(booking.start_time, booking.end_time),
    partySize: booking.party_size,
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link href={`/bookings/${id}`} className="text-sm text-indigo-600 hover:underline">
          ← กลับ
        </Link>
        <h1 className="text-2xl font-bold text-gray-900">แก้ไขการจอง</h1>
      </div>

      <div className="flex items-center gap-2">
        {STEP_LABELS.map((label, i) => {
          const n = (i + 1) as Step;
          const active = n === step;
          const done = n < step;
          return (
            <div key={n} className="flex items-center gap-2">
              <div
                className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${
                  done
                    ? "bg-indigo-600 text-white"
                    : active
                    ? "border-2 border-indigo-600 text-indigo-600"
                    : "border-2 border-gray-300 text-gray-400"
                }`}
              >
                {done ? "✓" : n}
              </div>
              <span
                className={`hidden text-sm sm:block ${
                  active ? "font-medium text-gray-900" : "text-gray-400"
                }`}
              >
                {label}
              </span>
              {i < STEP_LABELS.length - 1 && (
                <div className="mx-1 h-px w-6 bg-gray-300" />
              )}
            </div>
          );
        })}
      </div>

      <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
        {step === 1 && (
          <Step1
            initial={step1Data ?? initialStep1}
            bookingId={id}
            onNext={(d) => {
              setStep1Data(d);
              setStep(2);
            }}
          />
        )}
        {step === 2 && step1Data && (
          <Step2
            step1={step1Data}
            bookingId={id}
            currentTableId={booking.table_id}
            onNext={(t) => {
              setSelectedTable(t);
              setStep(3);
            }}
            onBack={() => setStep(1)}
          />
        )}
        {step === 3 && step1Data && selectedTable && (
          <Step3
            step1={step1Data}
            table={selectedTable}
            bookingId={id}
            initialSpecialRequests={booking.special_requests}
            onBack={() => setStep(2)}
          />
        )}
      </div>
    </div>
  );
}
