import { useId } from 'react';
import { useTranslation } from 'react-i18next';

/**
 * The engine's control code (TOTP from `CONTROL_TOTP_SECRET`, enrolled with `app.cli engine new-totp`). Not the
 * sign-in code: only the engine can check it, once, so a compromised cloud cannot close positions (PLAN §A13).
 */
export function EngineCodeField({ value, onChange }: { value: string; onChange: (code: string) => void }) {
  const { t } = useTranslation();
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className="block font-medium">
        {t('controls.engineCode')}
      </label>
      <p className="text-xs text-slate-500">{t('controls.engineCodeHint')}</p>
      <input
        id={id}
        inputMode="numeric"
        autoComplete="off"
        maxLength={6}
        value={value}
        onChange={(e) => {
          onChange(e.target.value.replace(/\D/g, ''));
        }}
        className="mt-1 w-32 rounded border border-slate-300 bg-white px-2 py-1 tracking-widest dark:border-slate-700 dark:bg-slate-950"
      />
    </div>
  );
}
