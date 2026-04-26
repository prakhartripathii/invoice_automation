import { useDispatch, useSelector } from 'react-redux';
import { useLocation } from 'react-router-dom';

import { logout } from '../../store/slices/authSlice.js';
import { setCurrency } from '../../store/slices/uiSlice.js';
import { SUPPORTED_CURRENCIES } from '../../utils/money.js';

const TITLES = {
  '/dashboard': 'Dashboard',
  '/invoices': 'Invoices',
  '/review': 'Review queue',
};

function initials(name = '') {
  return name
    .split(' ')
    .map((p) => p[0])
    .filter(Boolean)
    .slice(0, 2)
    .join('')
    .toUpperCase();
}

export default function Topbar() {
  const dispatch = useDispatch();
  const user = useSelector((s) => s.auth.user);
  const currency = useSelector((s) => s.ui.currency);
  const { pathname } = useLocation();
  const title =
    TITLES[pathname] ||
    (pathname.startsWith('/invoices/') ? 'Invoice detail' : 'DocuSense');

  return (
    <header className="topbar">
      <div className="topbar__title">{title}</div>
      <div className="topbar__user">
        <div
          className="currency-switcher"
          role="group"
          aria-label="Display currency"
          style={{
            display: 'inline-flex',
            border: '1px solid var(--color-border)',
            borderRadius: 8,
            overflow: 'hidden',
          }}
        >
          {SUPPORTED_CURRENCIES.map((c) => {
            const active = c === currency;
            return (
              <button
                key={c}
                type="button"
                onClick={() => dispatch(setCurrency(c))}
                aria-pressed={active}
                style={{
                  padding: '6px 12px',
                  fontSize: 12,
                  fontWeight: 600,
                  border: 'none',
                  background: active ? 'var(--color-primary)' : 'transparent',
                  color: active ? '#fff' : 'var(--color-text)',
                  cursor: 'pointer',
                }}
              >
                {c}
              </button>
            );
          })}
        </div>
        {user && (
          <>
            <div className="avatar" title={user.full_name}>
              {initials(user.full_name)}
            </div>
            <button className="btn btn--ghost" onClick={() => dispatch(logout())}>
              Sign out
            </button>
          </>
        )}
      </div>
    </header>
  );
}
