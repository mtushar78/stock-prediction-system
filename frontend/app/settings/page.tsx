'use client';

/**
 * /settings — account + admin console.
 *
 *  • Every signed-in user can change their own password.
 *  • Admins (the owner + any user flagged admin) additionally get a user
 *    management panel: create logins, reset any password, and impersonate a
 *    user (log in as them to see exactly what they see).
 */

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import axios from 'axios';
import {
  TrendingUp,
  KeyRound,
  UserPlus,
  Users,
  ShieldCheck,
  UserCog,
  Loader2,
  Check,
  RefreshCw,
} from 'lucide-react';
import { useAuth } from '../components/AuthProvider';
import {
  changePassword,
  adminListUsers,
  adminCreateUser,
  adminResetPassword,
  startImpersonation,
  AdminUser,
} from '../authClient';

function errMsg(e: unknown, fallback: string): string {
  if (axios.isAxiosError(e)) {
    const d = e.response?.data?.detail;
    if (typeof d === 'string') return d;
  }
  return fallback;
}

export default function SettingsPage() {
  const { user, isAdmin } = useAuth();

  return (
    <main className="min-h-screen bg-gray-950 text-gray-100 p-4 sm:p-6 lg:p-8">
      <header className="mb-6 flex items-center justify-between border-b border-gray-800 pb-4">
        <div>
          <h1 className="text-2xl font-bold text-green-400 flex items-center gap-2">
            <UserCog className="w-7 h-7" /> Settings
          </h1>
          <p className="text-gray-500 text-sm">
            Signed in as {user?.email}
            {isAdmin && <span className="ml-1 text-amber-400 font-semibold">· Admin</span>}
          </p>
        </div>
        <Link
          href="/"
          className="px-3 py-1.5 rounded bg-gray-800 text-gray-300 border border-gray-700 hover:bg-gray-700 hover:text-white transition flex items-center gap-1.5 text-sm"
        >
          <TrendingUp className="w-4 h-4" /> Dashboard
        </Link>
      </header>

      <div className="max-w-3xl mx-auto space-y-6">
        <ChangePasswordCard />
        {isAdmin && <AdminPanel />}
      </div>
    </main>
  );
}

// ------------------------------------------------------------------ //
// Change my password (all users)
// ------------------------------------------------------------------ //
function ChangePasswordCard() {
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setMsg(null);
    if (next.length < 4) {
      setMsg({ ok: false, text: 'New password must be at least 4 characters.' });
      return;
    }
    if (next !== confirm) {
      setMsg({ ok: false, text: 'New password and confirmation do not match.' });
      return;
    }
    setBusy(true);
    try {
      await changePassword(current, next);
      setMsg({ ok: true, text: 'Password changed.' });
      setCurrent('');
      setNext('');
      setConfirm('');
    } catch (e) {
      setMsg({ ok: false, text: errMsg(e, 'Could not change password.') });
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="bg-gray-900 border border-gray-800 rounded-xl p-5">
      <h2 className="text-lg font-semibold flex items-center gap-2 mb-4">
        <KeyRound className="w-5 h-5 text-green-400" /> Change my password
      </h2>
      <form onSubmit={submit} className="space-y-3 max-w-sm">
        <Field label="Current password" type="password" value={current} onChange={setCurrent} autoComplete="current-password" />
        <Field label="New password" type="password" value={next} onChange={setNext} autoComplete="new-password" />
        <Field label="Confirm new password" type="password" value={confirm} onChange={setConfirm} autoComplete="new-password" />
        {msg && (
          <div className={`text-sm rounded px-3 py-2 border ${msg.ok ? 'text-emerald-300 bg-emerald-950/40 border-emerald-900' : 'text-red-300 bg-red-950/40 border-red-900'}`}>
            {msg.text}
          </div>
        )}
        <button
          type="submit"
          disabled={busy || !current || !next}
          className="bg-green-600 hover:bg-green-700 disabled:bg-gray-700 text-white text-sm font-medium rounded px-4 py-2 flex items-center gap-2 transition"
        >
          {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
          Update password
        </button>
      </form>
    </section>
  );
}

// ------------------------------------------------------------------ //
// Admin: user management
// ------------------------------------------------------------------ //
function AdminPanel() {
  const { user } = useAuth();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadErr, setLoadErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadErr(null);
    try {
      setUsers(await adminListUsers());
    } catch (e) {
      setLoadErr(errMsg(e, 'Could not load users.'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <section className="bg-gray-900 border border-amber-900/40 rounded-xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <ShieldCheck className="w-5 h-5 text-amber-400" /> User management
          <span className="text-[10px] uppercase tracking-wide text-amber-400/80 border border-amber-800/60 rounded px-1.5 py-0.5">
            admin
          </span>
        </h2>
        <button
          onClick={load}
          className="text-gray-400 hover:text-white flex items-center gap-1 text-sm"
          title="Reload"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /> Reload
        </button>
      </div>

      <CreateUserForm onCreated={load} />

      <div className="mt-6">
        <h3 className="text-sm font-semibold text-gray-300 flex items-center gap-2 mb-2">
          <Users className="w-4 h-4" /> Users ({users.length})
        </h3>
        {loadErr && (
          <div className="text-sm text-red-300 bg-red-950/40 border border-red-900 rounded px-3 py-2 mb-2">
            {loadErr}
          </div>
        )}
        <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[560px]">
            <thead>
              <tr className="text-gray-500 text-xs border-b border-gray-800 text-left">
                <th className="py-2 pr-3">ID</th>
                <th className="py-2 pr-3">EMAIL</th>
                <th className="py-2 pr-3">ROLE</th>
                <th className="py-2 pr-3 text-right">ACTIONS</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <UserRow key={u.id} u={u} isSelf={u.id === user?.id} onChanged={load} />
              ))}
              {users.length === 0 && !loading && (
                <tr>
                  <td colSpan={4} className="py-6 text-center text-gray-600">
                    No users yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

function CreateUserForm({ onCreated }: { onCreated: () => void }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [admin, setAdmin] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setMsg(null);
    setBusy(true);
    try {
      const u = await adminCreateUser(email.trim(), password, admin);
      setMsg({ ok: true, text: `Created ${u.email}.` });
      setEmail('');
      setPassword('');
      setAdmin(false);
      onCreated();
    } catch (e) {
      setMsg({ ok: false, text: errMsg(e, 'Could not create user.') });
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="bg-gray-950/60 border border-gray-800 rounded-lg p-4">
      <h3 className="text-sm font-semibold text-gray-300 flex items-center gap-2 mb-3">
        <UserPlus className="w-4 h-4 text-emerald-400" /> Create a new user
      </h3>
      <div className="grid sm:grid-cols-2 gap-3">
        <Field label="Email" type="email" value={email} onChange={setEmail} placeholder="user@example.com" />
        <Field label="Password" type="text" value={password} onChange={setPassword} placeholder="min 4 characters" autoComplete="new-password" />
      </div>
      <label className="flex items-center gap-2 mt-3 text-sm text-gray-400 select-none cursor-pointer">
        <input type="checkbox" checked={admin} onChange={(e) => setAdmin(e.target.checked)} className="accent-amber-500" />
        Make this user an admin
      </label>
      {msg && (
        <div className={`mt-3 text-sm rounded px-3 py-2 border ${msg.ok ? 'text-emerald-300 bg-emerald-950/40 border-emerald-900' : 'text-red-300 bg-red-950/40 border-red-900'}`}>
          {msg.text}
        </div>
      )}
      <button
        type="submit"
        disabled={busy || !email.trim() || !password}
        className="mt-3 bg-emerald-600 hover:bg-emerald-700 disabled:bg-gray-700 text-white text-sm font-medium rounded px-4 py-2 flex items-center gap-2 transition"
      >
        {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <UserPlus className="w-4 h-4" />}
        Create user
      </button>
    </form>
  );
}

function UserRow({ u, isSelf, onChanged }: { u: AdminUser; isSelf: boolean; onChanged: () => void }) {
  const [resetting, setResetting] = useState(false);
  const [pw, setPw] = useState('');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const doReset = async () => {
    setMsg(null);
    setBusy(true);
    try {
      await adminResetPassword(u.id, pw);
      setMsg({ ok: true, text: 'Password reset.' });
      setPw('');
      setResetting(false);
      onChanged();
    } catch (e) {
      setMsg({ ok: false, text: errMsg(e, 'Reset failed.') });
    } finally {
      setBusy(false);
    }
  };

  const doImpersonate = async () => {
    setBusy(true);
    try {
      await startImpersonation(u.id);
      // Reload as the impersonated user; the banner + return button appear.
      window.location.assign('/');
    } catch (e) {
      setMsg({ ok: false, text: errMsg(e, 'Could not impersonate.') });
      setBusy(false);
    }
  };

  return (
    <>
      <tr className="border-b border-gray-800/60">
        <td className="py-2 pr-3 text-gray-500">{u.id}</td>
        <td className="py-2 pr-3 text-gray-200">
          {u.email}
          {isSelf && <span className="ml-1 text-[10px] text-gray-500">(you)</span>}
        </td>
        <td className="py-2 pr-3">
          {u.is_admin ? (
            <span className="text-[10px] bg-amber-600 text-white px-1.5 py-0.5 rounded font-bold">ADMIN</span>
          ) : (
            <span className="text-[10px] text-gray-500">user</span>
          )}
        </td>
        <td className="py-2 pr-3">
          <div className="flex items-center gap-2 justify-end">
            <button
              onClick={() => { setResetting((v) => !v); setMsg(null); }}
              className="text-xs text-blue-300 hover:text-blue-200"
            >
              Reset password
            </button>
            {!isSelf && (
              <button
                onClick={doImpersonate}
                disabled={busy}
                className="inline-flex items-center gap-1 text-xs bg-amber-600/90 hover:bg-amber-600 disabled:bg-gray-700 text-white rounded px-2 py-1 transition"
                title={`Log in as ${u.email}`}
              >
                <UserCog className="w-3.5 h-3.5" /> Impersonate
              </button>
            )}
          </div>
        </td>
      </tr>
      {(resetting || msg) && (
        <tr className="border-b border-gray-800/60">
          <td colSpan={4} className="py-2 pr-3">
            {resetting && (
              <div className="flex items-center gap-2 flex-wrap">
                <input
                  type="text"
                  value={pw}
                  onChange={(e) => setPw(e.target.value)}
                  placeholder={`New password for ${u.email}`}
                  className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm w-64 focus:outline-none focus:border-blue-500"
                />
                <button
                  onClick={doReset}
                  disabled={busy || pw.length < 4}
                  className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 text-white text-xs rounded px-3 py-1.5 flex items-center gap-1"
                >
                  {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
                  Set
                </button>
                <button onClick={() => { setResetting(false); setPw(''); }} className="text-xs text-gray-500 hover:text-gray-300">
                  cancel
                </button>
              </div>
            )}
            {msg && (
              <div className={`mt-1 text-xs ${msg.ok ? 'text-emerald-400' : 'text-red-400'}`}>{msg.text}</div>
            )}
          </td>
        </tr>
      )}
    </>
  );
}

// ------------------------------------------------------------------ //
function Field({
  label,
  type,
  value,
  onChange,
  placeholder,
  autoComplete,
}: {
  label: string;
  type: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  autoComplete?: string;
}) {
  return (
    <label className="block">
      <span className="block text-xs text-gray-400 mb-1">{label}</span>
      <input
        type={type}
        value={value}
        placeholder={placeholder}
        autoComplete={autoComplete}
        onChange={(e) => onChange(e.target.value)}
        className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-green-500"
      />
    </label>
  );
}
