/**
 * Trigger a browser download for an in-memory Blob.
 * Uses a temporary <a download> + ObjectURL — works in all evergreen browsers.
 */
export function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  // Revoke after the click event is queued so Safari/Firefox don't cancel.
  setTimeout(() => URL.revokeObjectURL(url), 0);
}
