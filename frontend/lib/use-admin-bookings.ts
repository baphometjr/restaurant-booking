import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

export interface AdminBookingItem {
  id: string;
  table_id: string;
  user_id: string;
  user_email: string;
  user_full_name: string;
  party_size: number;
  start_time: string;
  end_time: string;
  status: "confirmed" | "cancelled" | "completed" | "no_show";
  special_requests: string | null;
  created_at: string;
  table: {
    id: string;
    table_number: string;
    capacity: number;
    location: string | null;
  };
}

export interface AdminBookingsParams {
  status?: string;
  from_date?: string;
  to_date?: string;
  page?: number;
  limit?: number;
}

export interface AdminBookingsMeta {
  total: number;
  page: number;
  limit: number;
  total_pages: number;
}

export function useAdminBookings(params: AdminBookingsParams = {}) {
  const { status, from_date, to_date, page = 1, limit = 20 } = params;

  return useQuery<{ data: AdminBookingItem[]; meta: AdminBookingsMeta }>({
    queryKey: ["admin", "bookings", { status, from_date, to_date, page, limit }],
    queryFn: async () => {
      const searchParams = new URLSearchParams();
      if (status) searchParams.set("status", status);
      if (from_date) searchParams.set("from_date", from_date);
      if (to_date) searchParams.set("to_date", to_date);
      searchParams.set("page", String(page));
      searchParams.set("limit", String(limit));

      const res = await apiClient.get(`/admin/bookings?${searchParams.toString()}`);
      return { data: res.data.data as AdminBookingItem[], meta: res.data.meta as AdminBookingsMeta };
    },
    staleTime: 30_000,
  });
}
