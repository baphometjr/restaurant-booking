import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export const apiClient = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
});

let accessToken: string | null = null;
let isRefreshing = false;
let failQueue: Array<{
  resolve: (token: string) => void;
  reject: (err: unknown) => void;
}> = [];

export const setAccessToken = (token: string | null) => {
  accessToken = token;
};

export const getAccessToken = () => accessToken;

const processQueue = (err: unknown, token: string | null = null) => {
  failQueue.forEach((p) => (err ? p.reject(err) : p.resolve(token!)));
  failQueue = [];
};

apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (res) => res,
  async (error: AxiosError) => {
    const original = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    const isRefreshCall = original.url?.includes("/auth/refresh");
    if (error.response?.status !== 401 || original._retry || isRefreshCall) {
      return Promise.reject(error);
    }

    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        failQueue.push({ resolve, reject });
      }).then((token) => {
        original.headers.Authorization = `Bearer ${token}`;
        return apiClient(original);
      });
    }

    original._retry = true;
    isRefreshing = true;

    try {
      const { data } = await apiClient.post("/auth/refresh");
      const newToken: string = data.data.access_token;
      setAccessToken(newToken);
      processQueue(null, newToken);
      original.headers.Authorization = `Bearer ${newToken}`;
      return apiClient(original);
    } catch (refreshError) {
      processQueue(refreshError, null);
      setAccessToken(null);
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
      return Promise.reject(refreshError);
    } finally {
      isRefreshing = false;
    }
  }
);
