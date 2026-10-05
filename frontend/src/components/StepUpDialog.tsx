import { type ReactNode, type SubmitEvent, useEffect, useId, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ApiError } from '@/api/client';
import { useStepUp } from '@/auth/stepUp';
import { translateCode } from '@/i18n/codes';

export interface StepUpDialogProps {
  title: string;
  confirmLabel: string;
  /** What the action does, plus any fields of its own (a reason, for example). */
  children?: ReactNode;
  /** Red confirm button for actions that stop or close something. */
  danger?: boolean;
  /** The action's own fields: a message when they are not usable yet (checked before any request). */
  validate?: () => string | null;
  /** Runs the action once the step-up is fresh; the dialog closes when it resolves. */
  onConfirm: () => Promise<void>;
  onClose: () => void;
}

const CODE = /^\d{6}$/;

/**
 * A confirmation dialog for control actions (PLAN §A14 step-up): it asks for an authenticator code unless a
 * step-up from the last 5 minutes is still valid, confirms it, then runs the action. A 403 `step_up_required`
 * from the action asks for a code again.
 */
export function StepUpDialog({
  title,
  confirmLabel,
  children,
  danger,
  validate,
  onConfirm,
  onClose,
}: StepUpDialogProps) {
  const { t, i18n } = useTranslation();
  const titleId = useId();
  const codeId = useId();
  const first = useRef<HTMLInputElement>(null);
  const cancel = useRef<HTMLButtonElement>(null);
  const { active, verify, expire } = useStepUp();
  const [askCode, setAskCode] = useState(!active);
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const needCode = askCode || !active;

  useEffect(() => {
    (first.current ?? cancel.current)?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('keydown', onKey);
    };
  }, [onClose]);

  const failure = (err: unknown): string => {
    if (!(err instanceof ApiError)) return t('stepUp.network');
    if (i18n.exists(`codes:engine.${err.code}`)) return translateCode(i18n, 'engine', err.code);
    return t('stepUp.failed', { code: err.code });
  };

  const submit = async (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (busy) return;
    const invalid = validate?.() ?? null;
    if (invalid) {
      setError(invalid);
      return;
    }
    if (needCode && !CODE.test(code)) {
      setError(t('stepUp.codeHint'));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      if (needCode) {
        try {
          await verify(code);
        } catch (err) {
          setError(err instanceof ApiError && err.status === 400 ? t('stepUp.invalidCode') : failure(err));
          return;
        }
        setAskCode(false);
        setCode('');
      }
      try {
        await onConfirm();
      } catch (err) {
        if (err instanceof ApiError && err.code === 'step_up_required') {
          expire();
          setAskCode(true);
          setError(t('stepUp.expired'));
        } else {
          setError(failure(err));
        }
        return;
      }
      onClose();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        tabIndex={-1}
        aria-hidden="true"
        className="absolute inset-0 h-full w-full bg-slate-900/50"
        onClick={onClose}
      />
      <form
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onSubmit={(event) => void submit(event)}
        className="relative w-full max-w-md rounded-lg bg-white p-4 shadow-xl dark:bg-slate-900"
      >
        <h2 id={titleId} className="mb-2 text-lg font-semibold">
          {title}
        </h2>
        <div className="space-y-3 text-sm">{children}</div>
        {needCode && (
          <div className="mt-3">
            <label htmlFor={codeId} className="block text-sm font-medium">
              {t('stepUp.code')}
            </label>
            <p className="text-xs text-slate-500">{t('stepUp.why')}</p>
            <input
              ref={first}
              id={codeId}
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              value={code}
              onChange={(e) => {
                setCode(e.target.value.replace(/\D/g, ''));
              }}
              className="mt-1 w-32 rounded border border-slate-300 bg-white px-2 py-1 tracking-widest dark:border-slate-700 dark:bg-slate-950"
            />
          </div>
        )}
        {error && (
          <p role="alert" className="mt-3 text-sm text-red-700 dark:text-red-400">
            {error}
          </p>
        )}
        <div className="mt-4 flex justify-end gap-2">
          <button
            ref={cancel}
            type="button"
            onClick={onClose}
            className="rounded px-3 py-1.5 text-sm underline"
          >
            {t('stepUp.cancel')}
          </button>
          <button
            type="submit"
            disabled={busy}
            className={`rounded px-3 py-1.5 text-sm font-medium text-white disabled:opacity-60 ${danger ? 'bg-red-700 hover:bg-red-800' : 'bg-slate-800 hover:bg-slate-900 dark:bg-slate-700'}`}
          >
            {busy ? t('stepUp.working') : confirmLabel}
          </button>
        </div>
      </form>
    </div>
  );
}
