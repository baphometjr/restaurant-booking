"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { apiClient, setAccessToken } from "./api-client";

interface User {
  id: string;
  email: string;
  full_name: string;
  phone: string | null;
  role: "customer" | "staff" | "admin";
}

interface AuthState {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
}

interface AuthContextValue extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  register: (payload: RegisterPayload) => Promise<void>;
  logout: () => Promise<void>;
}

interface RegisterPayload {
  email: string;
  password: string;
  full_name: string;
  phone?: string;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchMe = useCallback(async () => {
    try {
      const { data } = await apiClient.get("/auth/me");
      setUser(data.data);
    } catch {
      setUser(null);
      setAccessToken(null);
    }
  }, []);

  // On mount: try silent refresh to restore session
  useEffect(() => {
    (async () => {
      try {
        const { data } = await apiClient.post("/auth/refresh");
        setAccessToken(data.data.access_token);
        await fetchMe();
      } catch {
        setUser(null);
      } finally {
        setIsLoading(false);
      }
    })();
  }, [fetchMe]);

  const login = useCallback(async (email: string, password: string) => {
    const { data } = await apiClient.post("/auth/login", { email, password });
    setAccessToken(data.data.access_token);
    await fetchMe();
  }, [fetchMe]);

  const register = useCallback(async (payload: RegisterPayload) => {
    await apiClient.post("/auth/register", payload);
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiClient.post("/auth/logout");
    } finally {
      setAccessToken(null);
      setUser(null);
    }
  }, []);

  return (
    <AuthContext.Provider
      value={{ user, isLoading, isAuthenticated: !!user, login, register, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
