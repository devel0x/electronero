import { useState } from 'react';
import { useRouter } from 'next/router';
import GlassContainer from '../components/GlassContainer';
import { useAuth } from '../context/AuthContext';
import api from '../lib/api';

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [inviteCode, setInviteCode] = useState('');
  const [mode, setMode] = useState('login');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError('');

    try {
      if (mode === 'register') {
        await api.register({ email, password, full_name: fullName, invite_code: inviteCode });
      }
      await login(email, password);
      router.push('/dashboard');
    } catch (err) {
      setError(err.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center py-12 px-6">
      <GlassContainer>
        <form onSubmit={handleSubmit} className="space-y-6 w-80">
          <div className="space-y-2 text-center">
            <h2 className="text-3xl neon-text">{mode === 'login' ? 'Login' : 'Register'}</h2>
            <p className="text-slate-400 text-sm">
              {mode === 'login'
                ? 'Authenticate with your operator account to access the portal.'
                : 'Create an account to start earning node operator rewards.'}
            </p>
          </div>
          <div className="space-y-4">
            <label className="block text-left text-sm">
              Email
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
                className="mt-1 w-full rounded-lg bg-slate-900/60 border border-slate-700 px-3 py-2 focus:outline-none focus:border-neon-blue"
              />
            </label>
            {mode === 'register' && (
              <label className="block text-left text-sm">
                Full Name
                <input
                  type="text"
                  value={fullName}
                  onChange={(event) => setFullName(event.target.value)}
                  required
                  className="mt-1 w-full rounded-lg bg-slate-900/60 border border-slate-700 px-3 py-2 focus:outline-none focus:border-neon-blue"
                />
              </label>
            )}
            <label className="block text-left text-sm">
              Password
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
                className="mt-1 w-full rounded-lg bg-slate-900/60 border border-slate-700 px-3 py-2 focus:outline-none focus:border-neon-pink"
              />
            </label>
            {mode === 'register' && (
              <label className="block text-left text-sm">
                Invitation Code
                <input
                  type="text"
                  value={inviteCode}
                  onChange={(event) => setInviteCode(event.target.value)}
                  placeholder="Required after initial bootstrap"
                  className="mt-1 w-full rounded-lg bg-slate-900/60 border border-slate-700 px-3 py-2 focus:outline-none focus:border-neon-blue"
                />
              </label>
            )}
          </div>
          {error && <p className="text-sm text-red-400">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2 rounded-full bg-gradient-to-r from-neon-pink to-neon-blue uppercase tracking-widest"
          >
            {loading ? 'Processing...' : mode === 'login' ? 'Login' : 'Create Account'}
          </button>
          <p className="text-center text-xs text-slate-400">
            {mode === 'login' ? 'Need an account?' : 'Already registered?'}{' '}
            <button
              type="button"
              onClick={() => setMode(mode === 'login' ? 'register' : 'login')}
              className="text-neon-blue hover:text-neon-pink"
            >
              {mode === 'login' ? 'Register here' : 'Back to login'}
            </button>
          </p>
        </form>
      </GlassContainer>
    </div>
  );
}
