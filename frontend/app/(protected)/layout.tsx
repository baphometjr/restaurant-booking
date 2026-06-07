"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth-context";

export default function ProtectedLayout({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login");
    }
  }, [isAuthenticated, isLoading, router]);

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-600 border-t-transparent" />
      </div>
    );
  }

  if (!isAuthenticated) return null;

  return (
    <div className="min-h-screen">
      <nav className="border-b border-gray-200 bg-white px-6 py-3">
        <div className="mx-auto flex max-w-5xl items-center justify-between">
          <span className="font-semibold text-gray-900">ระบบจองโต๊ะ</span>
          <NavLinks />
        </div>
      </nav>
      <main className="mx-auto max-w-5xl px-4 py-8">{children}</main>
    </div>
  );
}

function NavLinks() {
  const { user, logout } = useAuth();
  const router = useRouter();

  const handleLogout = async () => {
    await logout();
    router.replace("/login");
  };

  return (
    <div className="flex items-center gap-4 text-sm">
      <a href="/dashboard" className="text-gray-600 hover:text-gray-900">
        หน้าหลัก
      </a>
      <a href="/bookings" className="text-gray-600 hover:text-gray-900">
        การจองของฉัน
      </a>
      <a href="/bookings/new" className="rounded-lg bg-indigo-600 px-3 py-1.5 font-medium text-white hover:bg-indigo-700">
        จองโต๊ะ
      </a>
      {(user?.role === "staff" || user?.role === "admin") && (
        <a href="/admin/bookings" className="text-amber-600 hover:text-amber-800 font-medium">
          จัดการการจอง
        </a>
      )}
      <span className="text-gray-400">|</span>
      <span className="text-gray-700">{user?.full_name}</span>
      <button onClick={handleLogout} className="text-gray-500 hover:text-red-600">
        ออกจากระบบ
      </button>
    </div>
  );
}
