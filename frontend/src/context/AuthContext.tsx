import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react";
import { login as apiLogin, register as apiRegister, getCurrentUser, type UserInfo, type LoginRequest, type RegisterRequest } from "@/api/auth";
import { setAuthToken } from "@/api/client";

interface AuthState {
  user: UserInfo | null;
  loading: boolean;
  error: string | null;
}

interface AuthContextValue extends AuthState {
  login: (req: LoginRequest) => Promise<void>;
  register: (req: RegisterRequest) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const TOKEN_KEY = "cadence_token";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    loading: true,
    error: null,
  });

  // On mount, check for existing token
  useEffect(() => {
    const token = sessionStorage.getItem(TOKEN_KEY);
    if (token) {
      setAuthToken(token);
      getCurrentUser()
        .then((user) => setState({ user, loading: false, error: null }))
        .catch(() => {
          sessionStorage.removeItem(TOKEN_KEY);
          setAuthToken(null);
          setState({ user: null, loading: false, error: null });
        });
    } else {
      setState({ user: null, loading: false, error: null });
    }
  }, []);

  const login = useCallback(async (req: LoginRequest) => {
    setState((s) => ({ ...s, error: null, loading: true }));
    try {
      const res = await apiLogin(req);
      sessionStorage.setItem(TOKEN_KEY, res.token);
      setAuthToken(res.token);
      setState({ user: res.user, loading: false, error: null });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Login failed";
      setState({ user: null, loading: false, error: msg });
      throw err;
    }
  }, []);

  const register = useCallback(async (req: RegisterRequest) => {
    setState((s) => ({ ...s, error: null, loading: true }));
    try {
      const res = await apiRegister(req);
      sessionStorage.setItem(TOKEN_KEY, res.token);
      setAuthToken(res.token);
      setState({ user: res.user, loading: false, error: null });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Registration failed";
      setState({ user: null, loading: false, error: msg });
      throw err;
    }
  }, []);

  const logout = useCallback(() => {
    sessionStorage.removeItem(TOKEN_KEY);
    setAuthToken(null);
    setState({ user: null, loading: false, error: null });
  }, []);

  return (
    <AuthContext.Provider value={{ ...state, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
