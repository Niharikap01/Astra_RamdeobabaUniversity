import React, { useState } from "react";
import { Lock, Shield, User, AlertCircle, Stethoscope, Key } from "lucide-react";
import { useAuth } from "../context/AuthContext";

export const LoginModal: React.FC = () => {
  const { showLoginModal, login, isAuthenticated } = useAuth();
  const [username, setUsername] = useState("dr_clinician");
  const [password, setPassword] = useState("nightwatch2026");
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  if (!showLoginModal && isAuthenticated) {
    return null;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password) {
      setErrorMessage("Please enter both username and password.");
      return;
    }

    setIsLoading(true);
    setErrorMessage(null);

    try {
      await login(username.trim(), password);
    } catch (err: any) {
      console.error("Login failed:", err);
      setErrorMessage(err.message?.replace(/^API Error \[\d+\]:\s*/, "") || "Authentication failed. Check credentials.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleQuickFill = (u: string, p: string) => {
    setUsername(u);
    setPassword(p);
    setErrorMessage(null);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md animate-fadeIn">
      <div className="w-full max-w-md bg-slate-900/95 border border-slate-700/80 rounded-2xl shadow-2xl shadow-indigo-950/50 p-6 md:p-8 text-slate-100 relative overflow-hidden">
        {/* Top gradient glow */}
        <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-indigo-500 via-cyan-400 to-emerald-500" />

        {/* Header */}
        <div className="flex items-center gap-3 mb-6">
          <div className="w-12 h-12 rounded-xl bg-indigo-600/20 border border-indigo-500/40 flex items-center justify-center text-indigo-400">
            <Shield className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
              NightWatch
              <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 font-mono">
                RBAC
              </span>
            </h2>
            <p className="text-xs text-slate-400">Clinical Observatory Security Gateway</p>
          </div>
        </div>

        {errorMessage && (
          <div className="mb-5 p-3 rounded-xl bg-rose-950/50 border border-rose-500/40 text-rose-200 text-xs flex items-start gap-2.5">
            <AlertCircle className="w-4 h-4 flex-shrink-0 text-rose-400 mt-0.5" />
            <div>
              <p className="font-semibold">Authentication Error</p>
              <p className="text-rose-300/90 mt-0.5">{errorMessage}</p>
            </div>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5 flex items-center gap-1.5">
              <User className="w-3.5 h-3.5 text-slate-400" />
              Username / Clinician ID
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-3.5 py-2.5 bg-slate-800/80 border border-slate-700 rounded-xl text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all"
              placeholder="e.g. dr_clinician"
              required
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5 flex items-center gap-1.5">
              <Lock className="w-3.5 h-3.5 text-slate-400" />
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3.5 py-2.5 bg-slate-800/80 border border-slate-700 rounded-xl text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all"
              placeholder="Enter password"
              required
            />
          </div>

          {/* Quick Credential Presets for Reviewers & Judges */}
          <div className="pt-1">
            <span className="text-[11px] text-slate-400 font-medium block mb-1.5">Demo Accounts:</span>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => handleQuickFill("dr_clinician", "nightwatch2026")}
                className="flex-1 py-1.5 px-2.5 bg-slate-800/60 hover:bg-slate-800 border border-slate-700/70 hover:border-indigo-500/40 rounded-lg text-xs text-slate-300 flex items-center justify-center gap-1.5 transition-all text-[11px]"
              >
                <Stethoscope className="w-3 h-3 text-cyan-400" />
                Clinician (Dr. Reed)
              </button>
              <button
                type="button"
                onClick={() => handleQuickFill("admin", "nightwatch2026")}
                className="flex-1 py-1.5 px-2.5 bg-slate-800/60 hover:bg-slate-800 border border-slate-700/70 hover:border-indigo-500/40 rounded-lg text-xs text-slate-300 flex items-center justify-center gap-1.5 transition-all text-[11px]"
              >
                <Key className="w-3 h-3 text-indigo-400" />
                Administrator
              </button>
            </div>
          </div>

          <div className="pt-2">
            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-2.5 px-4 bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-500 hover:to-indigo-600 active:scale-[0.99] text-white text-sm font-semibold rounded-xl shadow-lg shadow-indigo-900/40 transition-all flex items-center justify-center gap-2 disabled:opacity-60 cursor-pointer"
            >
              {isLoading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                  <span>Verifying Credentials...</span>
                </>
              ) : (
                <>
                  <Lock className="w-4 h-4" />
                  <span>Access Clinical Digital Twin</span>
                </>
              )}
            </button>
          </div>
        </form>

        <p className="mt-5 text-[11px] text-center text-slate-500 leading-relaxed">
          Protected clinical decision support software. Activity is audited and tied to clinician identity.
        </p>
      </div>
    </div>
  );
};
