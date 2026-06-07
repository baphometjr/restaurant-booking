import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import type { BookingResponse } from "@/lib/types";

interface CreateBookingPayload {
  table_id: string;
  start_time: string;
  end_time: string;
  party_size: number;
  special_requests: string | null;
}

interface UpdateBookingPayload {
  table_id?: string;
  start_time?: string;
  end_time?: string;
  party_size?: number;
  special_requests?: string | null;
}

export function useMyBookings() {
  return useQuery<BookingResponse[]>({
    queryKey: ["bookings", "my"],
    queryFn: async () => {
      const res = await apiClient.get("/bookings/my");
      return res.data.data as BookingResponse[];
    },
    staleTime: 30_000,
  });
}

export function useBooking(id: string) {
  return useQuery<BookingResponse>({
    queryKey: ["bookings", id],
    queryFn: async () => {
      const res = await apiClient.get(`/bookings/${id}`);
      return res.data.data as BookingResponse;
    },
    enabled: Boolean(id),
  });
}

export function useCreateBooking() {
  const qc = useQueryClient();
  return useMutation<BookingResponse, Error, CreateBookingPayload>({
    mutationFn: async (payload) => {
      const res = await apiClient.post("/bookings", payload);
      return res.data.data as BookingResponse;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["bookings", "my"] });
    },
  });
}

export function useEditBooking(bookingId: string) {
  const qc = useQueryClient();
  return useMutation<BookingResponse, Error, UpdateBookingPayload>({
    mutationFn: async (payload) => {
      const res = await apiClient.patch(`/bookings/${bookingId}`, payload);
      return res.data.data as BookingResponse;
    },
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["bookings", "my"] });
      qc.setQueryData(["bookings", bookingId], data);
    },
  });
}

export function useCancelBooking() {
  const qc = useQueryClient();
  return useMutation<BookingResponse, Error, string>({
    mutationFn: async (bookingId) => {
      const res = await apiClient.post(`/bookings/${bookingId}/cancel`);
      return res.data.data as BookingResponse;
    },
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["bookings", "my"] });
      qc.setQueryData(["bookings", data.id], data);
    },
  });
}
