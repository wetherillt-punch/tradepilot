"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import api, { SessionResponse } from "@/lib/api";

// ─── Types ────────────────────────────────────────────────────────────────────

interface SessionState {
  sessionId: string | null;
  sessionData: SessionResponse | null;
  isLoading: boolean;
  error: string | null;
}

interface SessionContextType extends SessionState {
  initSession: () => Promise<void>;
  endSession: () => void;
  isActive: boolean;
}

// ─── Context ──────────────────────────────────────────────────────────────────

const SessionContext = createContext<SessionContextType | null>(null);

// ─── localStorage keys ────────────────────────────────────────────────────────

const STORAGE_KEY_ID = "tradepilot_session_id";
const STORAGE_KEY_DATA = "tradepilot_session_data";
const STORAGE_KEY_DATE = "tradepilot_session_date";

// ─── Helper: get today's date in ET ───────────────────────────────────────────

function getTodayET(): string {
  return new Date().toLocaleDateString("en-CA", { timeZone: "America/New_York" });
}

// ─── Provider ─────────────────────────────────────────────────────────────────

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<SessionState>({
    sessionId: null,
    sessionData: null,
    isLoading: false,
    error: null,
  });

  // Restore session from localStorage on mount
  useEffect(() => {
    try {
      const storedDate = localStorage.getItem(STORAGE_KEY_DATE);
      const todayET = getTodayET();

      // Session expires at midnight ET (new trading day)
      if (storedDate && storedDate !== todayET) {
        localStorage.removeItem(STORAGE_KEY_ID);
        localStorage.removeItem(STORAGE_KEY_DATA);
        localStorage.removeItem(STORAGE_KEY_DATE);
        return;
      }

      const storedId = localStorage.getItem(STORAGE_KEY_ID);
      const storedData = localStorage.getItem(STORAGE_KEY_DATA);

      if (storedId && storedData) {
        setState({
          sessionId: storedId,
          sessionData: JSON.parse(storedData),
          isLoading: false,
          error: null,
        });
      }
    } catch {
      // Corrupted localStorage — clear and start fresh
      localStorage.removeItem(STORAGE_KEY_ID);
      localStorage.removeItem(STORAGE_KEY_DATA);
      localStorage.removeItem(STORAGE_KEY_DATE);
    }
  }, []);

  // Initialize a new session
  const initSession = useCallback(async () => {
    setState((prev) => ({ ...prev, isLoading: true, error: null }));
    try {
      const res = await api.initSession([]);

      // Persist to localStorage
      localStorage.setItem(STORAGE_KEY_ID, res.session_id);
      localStorage.setItem(STORAGE_KEY_DATA, JSON.stringify(res));
      localStorage.setItem(STORAGE_KEY_DATE, getTodayET());

      setState({
        sessionId: res.session_id,
        sessionData: res,
        isLoading: false,
        error: null,
      });
    } catch (e: any) {
      setState((prev) => ({
        ...prev,
        isLoading: false,
        error: e.message || "Failed to initialize session",
      }));
    }
  }, []);

  // End session manually
  const endSession = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY_ID);
    localStorage.removeItem(STORAGE_KEY_DATA);
    localStorage.removeItem(STORAGE_KEY_DATE);
    setState({
      sessionId: null,
      sessionData: null,
      isLoading: false,
      error: null,
    });
  }, []);

  const value: SessionContextType = {
    ...state,
    initSession,
    endSession,
    isActive: !!state.sessionId,
  };

  return (
    <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
  );
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useSession(): SessionContextType {
  const ctx = useContext(SessionContext);
  if (!ctx) {
    throw new Error("useSession must be used within a SessionProvider");
  }
  return ctx;
}
