import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";

export default function LoginPage() {
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const [isRegistering, setIsRegistering] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleLoginSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login({ email, password });
      navigate("/projects");
    } catch {
      setError("Invalid email or password");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRegisterSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await register({ email, name, password, invite_code: inviteCode });
      navigate("/projects");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Registration failed";
      if (msg.includes("409")) {
        setError("Email already registered");
      } else if (msg.includes("403")) {
        setError("Invalid invite code");
      } else {
        setError(msg);
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-vellum flex items-center justify-center p-4">
      <div className="w-full max-w-[360px] bg-sheet border border-rule px-8 py-10">
        <h1 className="text-2xl font-semibold tracking-tight text-ink mb-1">
          Cadence
        </h1>
        <p className="text-sm text-graphite mb-8">
          Construction data reconciliation
        </p>

        {!isRegistering ? (
          // Login Form
          <form onSubmit={handleLoginSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-graphite mb-1">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoFocus
                className="w-full px-3 py-2 text-sm bg-sheet border border-rule text-ink
                           focus:outline-none focus:border-ink transition-colors"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-graphite mb-1">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full px-3 py-2 text-sm bg-sheet border border-rule text-ink
                           focus:outline-none focus:border-ink transition-colors"
              />
            </div>

            {error && (
              <p className="text-sm text-redline-ink">{error}</p>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="w-full py-2 text-sm font-medium bg-ink text-sheet
                         hover:bg-ink/90 transition-colors disabled:opacity-50"
            >
              {submitting ? "Signing in…" : "Sign in"}
            </button>

            <p className="text-center text-xs text-graphite mt-6">
              Have an invite code?{" "}
              <button
                type="button"
                onClick={() => {
                  setIsRegistering(true);
                  setError(null);
                  setEmail("");
                  setPassword("");
                }}
                className="text-ink hover:underline font-medium"
              >
                Create an account
              </button>
            </p>
          </form>
        ) : (
          // Registration Form
          <form onSubmit={handleRegisterSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-graphite mb-1">
                Name
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                autoFocus
                className="w-full px-3 py-2 text-sm bg-sheet border border-rule text-ink
                           focus:outline-none focus:border-ink transition-colors"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-graphite mb-1">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full px-3 py-2 text-sm bg-sheet border border-rule text-ink
                           focus:outline-none focus:border-ink transition-colors"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-graphite mb-1">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full px-3 py-2 text-sm bg-sheet border border-rule text-ink
                           focus:outline-none focus:border-ink transition-colors"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-graphite mb-1">
                Invite Code
              </label>
              <input
                type="text"
                value={inviteCode}
                onChange={(e) => setInviteCode(e.target.value)}
                required
                className="w-full px-3 py-2 text-sm bg-sheet border border-rule text-ink
                           focus:outline-none focus:border-ink transition-colors"
              />
            </div>

            {error && (
              <p className="text-sm text-redline-ink">{error}</p>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="w-full py-2 text-sm font-medium bg-ink text-sheet
                         hover:bg-ink/90 transition-colors disabled:opacity-50"
            >
              {submitting ? "Creating account…" : "Create account"}
            </button>

            <p className="text-center text-xs text-graphite mt-6">
              Already have an account?{" "}
              <button
                type="button"
                onClick={() => {
                  setIsRegistering(false);
                  setError(null);
                  setName("");
                  setInviteCode("");
                  setEmail("");
                  setPassword("");
                }}
                className="text-ink hover:underline font-medium"
              >
                Sign in
              </button>
            </p>
          </form>
        )}
      </div>
    </div>
  );
}
