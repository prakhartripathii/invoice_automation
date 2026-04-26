/**
 * Batches slice — tracks upload batch sessions on the client.
 *
 * The backend does not (yet) have a batch concept. We treat each `UploadDropzone`
 * drop event as one batch: a session id is created, every uploaded invoice is
 * appended to it, and the result is persisted to localStorage so the user can
 * revisit past batches.
 *
 * Shape of a batch:
 *   {
 *     id: string,                  // 'batch_<timestamp>_<rand>'
 *     timestamp: ISO string,       // when the batch started
 *     totalInvoices: number,       // how many files were dropped (target count)
 *     invoices: Invoice[],         // server responses appended as they complete
 *   }
 */
import { createSlice } from '@reduxjs/toolkit';

const STORAGE_KEY = 'invoice.batches';
const MAX_BATCHES = 50; // cap localStorage growth

function loadFromStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed;
  } catch {
    return [];
  }
}

function persist(batches) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(batches.slice(0, MAX_BATCHES)));
  } catch {
    // localStorage may be full or unavailable; silently ignore
  }
}

const initialState = {
  /** Most recent first. */
  batches: loadFromStorage(),
  /** id of the batch currently being viewed in the Upload page. null = latest. */
  activeBatchId: null,
};

const batchesSlice = createSlice({
  name: 'batches',
  initialState,
  reducers: {
    startBatch: {
      reducer(state, { payload }) {
        state.batches.unshift(payload);
        state.activeBatchId = payload.id;
        persist(state.batches);
      },
      prepare(totalInvoices) {
        const id = `batch_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
        return {
          payload: {
            id,
            timestamp: new Date().toISOString(),
            totalInvoices,
            invoices: [],
          },
        };
      },
    },
    appendInvoiceToBatch(state, { payload }) {
      // payload: { batchId, invoice }
      const b = state.batches.find((x) => x.id === payload.batchId);
      if (b) {
        b.invoices.push(payload.invoice);
        persist(state.batches);
      }
    },
    /**
     * Replace an entire batch's invoices array. Useful for refreshing statuses
     * via a polling fetch after upload completes.
     */
    updateBatchInvoices(state, { payload }) {
      const b = state.batches.find((x) => x.id === payload.batchId);
      if (b) {
        b.invoices = payload.invoices;
        persist(state.batches);
      }
    },
    setActiveBatch(state, { payload }) {
      state.activeBatchId = payload;
    },
    clearBatches(state) {
      state.batches = [];
      state.activeBatchId = null;
      persist(state.batches);
    },
  },
});

export const {
  startBatch,
  appendInvoiceToBatch,
  updateBatchInvoices,
  setActiveBatch,
  clearBatches,
} = batchesSlice.actions;

/* ---------------- Selectors ---------------- */

export const selectAllBatches = (s) => s.batches.batches;

export const selectActiveBatch = (s) => {
  const { batches, activeBatchId } = s.batches;
  if (!batches.length) return null;
  if (!activeBatchId) return batches[0]; // latest by default
  return batches.find((b) => b.id === activeBatchId) || batches[0];
};

export default batchesSlice.reducer;
