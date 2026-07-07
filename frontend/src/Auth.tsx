import { useState } from "react";
import { login, register } from "./api";

interface AuthProps {
  onAuthenticated: (token: string) => void;
}

export default function Auth({ onAuthenticated }: AuthProps) {
  const [isRegister, setIsRegister] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const result = isRegister
        ? await register(username, password)
        : await login(username, password);
      onAuthenticated(result.access_token);
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "Something went wrong";
      setError(detail);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0f0f0f]">
      <div className="w-full max-w-md px-8">
        {/* Logo */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-br from-blue-500 to-violet-600 mb-4 shadow-lg">
            <span className="text-white font-bold text-xl">E</span>
          </div>
          <h1 className="text-3xl font-bold text-white tracking-tight">EADA</h1>
          <p className="text-gray-400 text-sm mt-1">Enterprise Autonomous Data Analyst</p>
        </div>

        {/* Card */}
        <div className="bg-[#1a1a1a] border border-white/10 rounded-2xl p-8 shadow-2xl">
          <h2 className="text-white font-semibold text-lg mb-6">
            {isRegister ? "Create your account" : "Welcome back"}
          </h2>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div>
              <label className="text-gray-400 text-xs font-medium mb-1.5 block uppercase tracking-wider">
                Username
              </label>
              <input
                type="text"
                placeholder="Enter your username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                className="w-full bg-[#262626] text-white rounded-xl px-4 py-3 outline-none
                           border border-white/10 focus:border-blue-500 focus:ring-1 focus:ring-blue-500
                           placeholder-gray-600 text-sm transition"
              />
            </div>

            <div>
              <label className="text-gray-400 text-xs font-medium mb-1.5 block uppercase tracking-wider">
                Password
              </label>
              <input
                type="password"
                placeholder="Enter your password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full bg-[#262626] text-white rounded-xl px-4 py-3 outline-none
                           border border-white/10 focus:border-blue-500 focus:ring-1 focus:ring-blue-500
                           placeholder-gray-600 text-sm transition"
              />
            </div>

            {error && (
              <div className="bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3">
                <p className="text-red-400 text-sm">{error}</p>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-gradient-to-r from-blue-600 to-violet-600 hover:from-blue-500
                         hover:to-violet-500 disabled:opacity-50 text-white rounded-xl px-4 py-3
                         font-semibold transition text-sm shadow-lg mt-2"
            >
              {loading ? "Please wait..." : isRegister ? "Create Account" : "Sign In"}
            </button>
          </form>

          <div className="mt-6 text-center">
            <button
              onClick={() => { setIsRegister(!isRegister); setError(""); }}
              className="text-gray-400 hover:text-white text-sm transition"
            >
              {isRegister
                ? "Already have an account? "
                : "Don't have an account? "}
              <span className="text-blue-400 hover:text-blue-300 font-medium">
                {isRegister ? "Sign In" : "Register"}
              </span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}