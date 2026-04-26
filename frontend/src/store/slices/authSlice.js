import { createAsyncThunk, createSlice } from '@reduxjs/toolkit';
import toast from 'react-hot-toast';

import { authApi, tokenStorage } from '../../services/api.js';

// When the mock adapter is active we pre-authenticate as a seeded admin so the
// UI can be demoed without a backend or login screen. This is a dev-only path —
// guarded by VITE_USE_MOCK_API so production builds never ship it.
const MOCK_MODE = import.meta.env.VITE_USE_MOCK_API === 'true';

const MOCK_USER = {
  id: '00000000-0000-0000-0000-000000000001',
  email: 'admin@invoiceapp.com',
  full_name: 'Ada Admin',
  role: 'ADMIN',
  is_active: true,
  created_at: '2026-01-01T09:00:00Z',
};

const initialState = MOCK_MODE
  ? {
      user: MOCK_USER,
      status: 'authenticated',
      initialized: true,
      error: null,
    }
  : {
      user: null,
      status: 'idle',        // idle | loading | authenticated | error
      initialized: false,    // has the initial "me" check completed?
      error: null,
    };

if (MOCK_MODE) {
  // Give the mock API adapter a token so any authenticated call (e.g. /auth/me)
  // succeeds on refresh without bouncing through the login screen.
  tokenStorage.set({ access_token: 'mock-access', refresh_token: 'mock-refresh' });
}

export const login = createAsyncThunk(
  'auth/login',
  async ({ email, password }, { rejectWithValue }) => {
    try {
      const tokens = await authApi.login(email, password);
      tokenStorage.set(tokens);
      const user = await authApi.me();
      toast.success(`Welcome back, ${user.full_name}`);
      return user;
    } catch (err) {
      const msg = err.response?.data?.message || 'Login failed';
      toast.error(msg);
      return rejectWithValue(msg);
    }
  },
);

export const loadSession = createAsyncThunk(
  'auth/loadSession',
  async (_, { rejectWithValue }) => {
    if (!tokenStorage.get()) return null;
    try {
      return await authApi.me();
    } catch {
      tokenStorage.clear();
      return rejectWithValue('Session expired');
    }
  },
);

const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    logout(state) {
      tokenStorage.clear();
      state.user = null;
      state.status = 'idle';
    },
  },
  extraReducers: (b) => {
    b.addCase(login.pending, (s) => {
      s.status = 'loading';
      s.error = null;
    });
    b.addCase(login.fulfilled, (s, a) => {
      s.user = a.payload;
      s.status = 'authenticated';
      s.initialized = true;
    });
    b.addCase(login.rejected, (s, a) => {
      s.status = 'error';
      s.error = a.payload;
    });
    b.addCase(loadSession.fulfilled, (s, a) => {
      s.user = a.payload;
      s.status = a.payload ? 'authenticated' : 'idle';
      s.initialized = true;
    });
    b.addCase(loadSession.rejected, (s) => {
      s.user = null;
      s.status = 'idle';
      s.initialized = true;
    });
  },
});

export const { logout } = authSlice.actions;
export default authSlice.reducer;
