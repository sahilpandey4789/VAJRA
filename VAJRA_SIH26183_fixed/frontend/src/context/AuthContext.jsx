import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import * as api from "../console-core/api.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [officer, setOfficer] = useState(null);
  const [booting, setBooting] = useState(true);

  useEffect(() => {
    (async () => {
      await api.detectMode();
      // Access token is memory-only (doesn't survive reload) - attempt a
      // silent restore off the refresh token left in sessionStorage.
      const restored = await api.restoreSession();
      if (restored) setOfficer(restored);
      setBooting(false);
    })();
  }, []);

  const login = useCallback(async (code, password) => {
    const off = await api.login(code, password);
    setOfficer(off);
    return off;
  }, []);

  const register = useCallback(async (fields) => {
    const off = await api.register(fields);
    setOfficer(off);
    return off;
  }, []);

  const logout = useCallback(async () => {
    await api.logout();
    setOfficer(null);
  }, []);

  return (
    <AuthContext.Provider value={{ officer, booting, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
