import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import api from '../lib/api';

const AuthContext = createContext({
  user: null,
  token: null,
  loading: true,
  login: async () => {},
  logout: () => {},
  refresh: async () => {},
});

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const stored = window.localStorage.getItem('ic:session');
    if (stored) {
      try {
        const parsed = JSON.parse(stored);
        setToken(parsed.token);
        setUser(parsed.user);
      } catch (err) {
        window.localStorage.removeItem('ic:session');
      }
    }
    setLoading(false);
  }, []);

  const login = async (email, password) => {
    setLoading(true);
    try {
      const session = await api.login({ email, password });
      setToken(session.access_token);
      setUser(session.user);
      window.localStorage.setItem('ic:session', JSON.stringify({ token: session.access_token, user: session.user }));
      return session.user;
    } finally {
      setLoading(false);
    }
  };

  const logout = () => {
    setToken(null);
    setUser(null);
    window.localStorage.removeItem('ic:session');
  };

  const refresh = async () => {
    if (!token) return;
    const me = await api.me(token);
    setUser(me);
    window.localStorage.setItem('ic:session', JSON.stringify({ token, user: me }));
  };

  const value = useMemo(
    () => ({ user, token, loading, login, logout, refresh }),
    [user, token, loading]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
