/** Generic API response types */

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface ApiResponse<T> {
  data: T | null;
  message: string;
}
