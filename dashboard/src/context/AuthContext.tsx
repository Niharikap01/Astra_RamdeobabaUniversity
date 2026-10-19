import React, { createContext, useContext, useEffect, useState } from "react";
import { AuthUser } from "../types";
import { api, getAuthToken, getStoredUser, setAuthToken, setStoredUser } from "../services/api";

interface AuthContextType {
  user: AuthUser | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  showLoginModal: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  openLoginModal: () => void;
  closeLoginModal: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [token, setTokenState] = useState<string | null>(getAuthToken());
  const [user, setUserState] = useState<AuthUser | null>(getStoredUser());
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [showLoginModal, setShowLoginModal] = useState<boolean>(false);

  useEffect(() => {
    const initAuth = async () => {
      const storedToken = getAuthToken();
      if (!storedToken) {
        setIsLoading(false);
        // Prompt login if no token
        setShowLoginModal(true);
        return;
      }

      try {
        const currentUser = await api.getMe();
        setUserState(currentUser);
        setStoredUser(currentUser);
      } catch (err) {
        console.warn("Stored auth token verification failed, clearing auth session:", err);
        setAuthToken(null);
        setStoredUser(null);
        setTokenState(null);
        setUserState(null);
        setShowLoginModal(true);
      } finally {
        setIsLoading(false);
      }
    };

    initAuth();

    // Listen for unauthorized 401 events dispatched from API calls
    const handleUnauthorized = () => {
      setAuthToken(null);
      setStoredUser(null);
      setTokenState(null);
      setUserState(null);
      setShowLoginModal(true);
    };

    window.addEventListener("nightwatch:unauthorized", handleUnauthorized);
    return () => {
      window.removeEventListener("nightwatch:unauthorized", handleUnauthorized);
    };
  }, []);

  const login = async (username: string, password: string) => {
    const res = await api.login(username, password);
    setAuthToken(res.access_token);
    setStoredUser(res.user);
    setTokenState(res.access_token);
    setUserState(res.user);
    setShowLoginModal(false);
  };

  const logout = () => {
    setAuthToken(null);
    setStoredUser(null);
    setTokenState(null);
    setUserState(null);
    setShowLoginModal(true);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!token && !!user,
        isLoading,
        showLoginModal,
        login,
        logout,
        openLoginModal: () => setShowLoginModal(true),
        closeLoginModal: () => {
          if (token && user) setShowLoginModal(false);
        },
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
