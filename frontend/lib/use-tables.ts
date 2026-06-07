import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import type { TableInfo } from "@/lib/types";

interface AvailableTablesParams {
  start_time: string;
  end_time: string;
  party_size: number;
  exclude_booking_id?: string;
}

export function useAvailableTables(params: AvailableTablesParams | null) {
  return useQuery<TableInfo[]>({
    queryKey: ["tables", "available", params],
    queryFn: async () => {
      if (!params) return [];
      const res = await apiClient.get("/tables/available", { params });
      return res.data.data as TableInfo[];
    },
    enabled: params !== null,
    staleTime: 30_000,
  });
}
