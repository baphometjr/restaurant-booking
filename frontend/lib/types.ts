export interface TableInfo {
  id: string;
  table_number: string;
  capacity: number;
  location: string | null;
}

export interface BookingResponse {
  id: string;
  table_id: string;
  party_size: number;
  start_time: string;
  end_time: string;
  status: "confirmed" | "cancelled" | "completed" | "no_show";
  special_requests: string | null;
  created_at: string;
  table: TableInfo;
}
