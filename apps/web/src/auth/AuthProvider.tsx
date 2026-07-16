import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState
} from "react";

import {
  AuthApiError,
  createAuthApi,
  type AuthApi,
  type SessionResponse
} from "./authApi";

export type AuthStatus = "checking" | "unauthenticated" | "authenticated" | "retryable_error";

export interface AuthState {
  error: AuthApiError | null;
  logout(): Promise<void>;
  refresh(): Promise<void>;
  retry(): Promise<void>;
  session: SessionResponse | null;
  startGoogle(): void;
  status: AuthStatus;
}

interface AuthProviderProps {
  api?: AuthApi;
  children: ReactNode;
}

interface AuthSnapshot {
  error: AuthApiError | null;
  session: SessionResponse | null;
  status: AuthStatus;
}

const browserAuthApi = createAuthApi();
const AuthContext = createContext<AuthState | null>(null);

function normalizedError(error: unknown): AuthApiError {
  return error instanceof AuthApiError
    ? error
    : new AuthApiError(0, "network_unavailable");
}

export function AuthProvider({ api = browserAuthApi, children }: AuthProviderProps) {
  const [snapshot, setSnapshot] = useState<AuthSnapshot>({
    error: null,
    session: null,
    status: "checking"
  });

  const loadSession = useCallback(async () => {
    setSnapshot((current) => ({ ...current, error: null, status: "checking" }));
    try {
      const session = await api.getSession();
      setSnapshot({ error: null, session, status: "authenticated" });
    } catch (reason) {
      const error = normalizedError(reason);
      setSnapshot({
        error: error.status === 401 ? null : error,
        session: null,
        status: error.status === 401 ? "unauthenticated" : "retryable_error"
      });
    }
  }, [api]);

  useEffect(() => {
    void loadSession();
  }, [loadSession]);

  const refresh = useCallback(async () => {
    if (snapshot.session === null) return;
    try {
      const refreshed = await api.refreshSession(snapshot.session.csrf_token);
      setSnapshot((current) =>
        current.session === null
          ? current
          : {
              error: null,
              session: {
                ...current.session,
                csrf_token: refreshed.csrf_token,
                session_version: refreshed.session_version
              },
              status: "authenticated"
            }
      );
    } catch (reason) {
      const error = normalizedError(reason);
      setSnapshot((current) => ({
        error: error.status === 401 ? null : error,
        session: error.status === 401 ? null : current.session,
        status: error.status === 401 ? "unauthenticated" : "retryable_error"
      }));
    }
  }, [api, snapshot.session]);

  const logout = useCallback(async () => {
    if (snapshot.session === null) return;
    try {
      await api.logout(snapshot.session.csrf_token);
      setSnapshot({ error: null, session: null, status: "unauthenticated" });
    } catch (reason) {
      const error = normalizedError(reason);
      setSnapshot((current) =>
        error.status === 401
          ? { error: null, session: null, status: "unauthenticated" }
          : { ...current, error, status: "retryable_error" }
      );
    }
  }, [api, snapshot.session]);

  const value = useMemo<AuthState>(
    () => ({
      ...snapshot,
      logout,
      refresh,
      retry: loadSession,
      startGoogle: api.startGoogle
    }),
    [api.startGoogle, loadSession, logout, refresh, snapshot]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const state = useContext(AuthContext);
  if (state === null) throw new Error("auth_provider_missing");
  return state;
}
