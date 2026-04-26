/**
 * Drag-and-drop upload component.
 *
 * Each drop event = one batch. We:
 *   1. dispatch `startBatch(totalCount)`  → creates a session record
 *   2. upload files serially so progress bar is meaningful
 *   3. append every server-side invoice response to that batch
 *   4. refresh global stats + invoice list at the end
 */
import { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { useDispatch, useSelector } from 'react-redux';

import { uploadInvoice, fetchStats, fetchInvoices } from '../../store/slices/invoicesSlice.js';
import { startBatch, appendInvoiceToBatch } from '../../store/slices/batchesSlice.js';

const ACCEPTED = {
  'application/pdf': ['.pdf'],
  'image/png': ['.png'],
  'image/jpeg': ['.jpg', '.jpeg'],
  'image/tiff': ['.tif', '.tiff'],
};

export default function UploadDropzone() {
  const dispatch = useDispatch();
  const { uploading, uploadProgress } = useSelector((s) => s.invoices);

  const onDrop = useCallback(
    async (accepted) => {
      if (!accepted.length) return;

      // 1. Open a new batch session
      const action = dispatch(startBatch(accepted.length));
      const batchId = action.payload.id;

      // 2. Upload serially so the progress bar reflects per-file progress
      for (const file of accepted) {
        const result = await dispatch(uploadInvoice(file));
        if (result.payload && result.meta?.requestStatus === 'fulfilled') {
          dispatch(appendInvoiceToBatch({ batchId, invoice: result.payload }));
        }
      }

      // 3. Refresh global aggregates
      dispatch(fetchStats());
      dispatch(fetchInvoices());
    },
    [dispatch],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED,
    maxSize: 25 * 1024 * 1024,
    multiple: true,
    disabled: uploading,
  });

  return (
    <div
      {...getRootProps({
        className: `dropzone ${isDragActive ? 'dropzone--active' : ''}`,
      })}
      aria-label="Upload invoice files"
    >
      <input {...getInputProps()} />
      <div className="dropzone__icon">⇪</div>
      <h3>{uploading ? 'Uploading…' : 'Drop invoices here, or click to browse'}</h3>
      <p>Supports PDF, PNG, JPEG and TIFF — up to 25 MB per file</p>
      {uploading && (
        <div className="progress" aria-label="Upload progress">
          <div className="progress__bar" style={{ width: `${uploadProgress}%` }} />
        </div>
      )}
    </div>
  );
}
