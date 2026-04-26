import { createSlice } from '@reduxjs/toolkit';

const uiSlice = createSlice({
  name: 'ui',
  initialState: {
    sidebarCollapsed: false,
    theme: 'light',
    currency: 'USD',
  },
  reducers: {
    toggleSidebar(state) {
      state.sidebarCollapsed = !state.sidebarCollapsed;
    },
    setTheme(state, { payload }) {
      state.theme = payload;
    },
    setCurrency(state, { payload }) {
      state.currency = payload;
    },
  },
});

export const { toggleSidebar, setTheme, setCurrency } = uiSlice.actions;
export default uiSlice.reducer;
