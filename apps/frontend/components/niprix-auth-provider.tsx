"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { AppShell } from "@/components/app-shell";
import { LoginScreen } from "@/components/login-screen";
import NiprixLoader from "@/components/niprix-loader";

import {
  api,
  clearTokens,
  hasStoredSession,
  preloadSalesSectionData,
  saveTokens,
  setCacheScope,
} from "@/lib/api";

import type { User } from "@/lib/types";

type NiprixAuthContextValue = {
  user: User;
};

const NiprixAuthContext = createContext<NiprixAuthContextValue | null>(null);

/**
 * This provider deliberately lives in the root layout.  App Router page changes
 * therefore keep one authenticated shell and one session restoration attempt
 * instead of remounting both for every CRM route.
 */
export function NiprixAuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [checking, setChecking] = useState(true);
  const [error, setError] = useState("");
  const initialized = useRef(false);

  const restore = useCallback(async () => {
    if (!hasStoredSession()) {
      setChecking(false);
      return;
    }

    try {
      const restoredUser = await api.me();
      setCacheScope(restoredUser);
setUser(restoredUser);
preloadSalesSectionData(restoredUser.role);

    } catch (caught) {
      clearTokens();
      setError(caught instanceof Error ? `Your saved session could not be restored. ${caught.message}` : "Your saved session could not be restored. Please sign in again.");
    } finally {
      setChecking(false);
    }
  }, []);

  useEffect(() => {
    // React Strict Mode replays effects in development. Keep restoration to one
    // request while still registering the unauthorized-event listener.
    if (!initialized.current) {
      initialized.current = true;
      void restore();
    }

    const unauthorized = () => {
      clearTokens();
      setUser(null);
      setError("Your session has ended. Please sign in again.");
    };
    window.addEventListener("niprix:unauthorized", unauthorized);
    return () => window.removeEventListener("niprix:unauthorized", unauthorized);
  }, [restore]);

  const login = useCallback(async (username: string, password: string) => {
    setError("");
    try {
      saveTokens(await api.login(username, password));
      const signedInUser = await api.me();
      setCacheScope(signedInUser);
      setUser(signedInUser);
      preloadSalesSectionData(signedInUser.role);

    } catch (caught) {
      clearTokens();
      setError(caught instanceof Error ? caught.message : "Unable to sign in. Please try again.");
      throw caught;
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
      setError("");
    } catch (caught) {
      setError(caught instanceof Error ? `You have been signed out locally. ${caught.message}` : "You have been signed out locally, but the server could not be reached.");
    } finally {
      clearTokens();
      setUser(null);
    }
  }, []);

  if (checking) return <NiprixLoader />;
  if (!user) return <LoginScreen onSubmit={login} error={error} />;

  return (
    <NiprixAuthContext.Provider value={{ user }}>
      <AppShell user={user} onLogout={() => void logout()}>{children}</AppShell>
    </NiprixAuthContext.Provider>
  );
}

export function useNiprixAuth() {
  const context = useContext(NiprixAuthContext);
  if (!context) throw new Error("useNiprixAuth must be used within NiprixAuthProvider.");
  return context;
}
