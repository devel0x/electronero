import { useState } from 'react';
import { useRouter } from 'next/router';
import axios from 'axios';
import GlassContainer from '../components/GlassContainer';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [mode, setMode] = useState('login');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError('');

    try {
      if (mode === 'register') {
        await axios.post(`${API_BASE}/users/register`, { email, password });
      }
      const response = await axios.post(`${API_BASE}/users/login`, { email, password });
      localStorage.setItem('token', response.data.access_token);
      router.push('/dashboard');
    } catch (err) {
      setError(err.response?.data?.detail || 'Authentication failed');
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
