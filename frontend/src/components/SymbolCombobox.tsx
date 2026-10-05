import { type KeyboardEvent, useId, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { filterSymbols, MAX_SHOWN, type SymbolOption } from './symbolFilter';

const INPUT =
  'w-40 rounded border border-slate-300 bg-white px-2 py-1 text-sm dark:border-slate-700 dark:bg-slate-900';

/** A searchable symbol picker (ARIA 1.2 combobox with a listbox popup). */
export function SymbolCombobox({
  label,
  value,
  options,
  featuredLabel,
  onChange,
}: {
  label: string;
  value: string | null;
  options: readonly SymbolOption[];
  /** Screen-reader and badge text for featured options. */
  featuredLabel: string;
  onChange: (symbol: string) => void;
}) {
  const { t } = useTranslation();
  const listId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);

  const matches = useMemo(() => filterSymbols(options, query), [options, query]);
  const shown = matches.slice(0, MAX_SHOWN);
  const optionId = (i: number) => `${listId}-${String(i)}`;

  const openList = () => {
    setQuery('');
    setActive(0);
    setOpen(true);
  };
  const close = () => {
    setOpen(false);
    setQuery('');
  };
  const choose = (symbol: string) => {
    close();
    if (symbol !== value) onChange(symbol);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      if (!open) {
        openList();
        return;
      }
      const step = event.key === 'ArrowDown' ? 1 : -1;
      setActive((i) => Math.min(Math.max(i + step, 0), Math.max(shown.length - 1, 0)));
    } else if (event.key === 'Enter' && open) {
      event.preventDefault();
      const picked = shown[active];
      if (picked) choose(picked.symbol);
    } else if (event.key === 'Escape' && open) {
      event.preventDefault();
      close();
    }
  };

  return (
    <div className="relative flex items-center gap-1.5 text-sm">
      <label htmlFor={`${listId}-input`}>{label}</label>
      <input
        ref={inputRef}
        id={`${listId}-input`}
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={open && shown[active] ? optionId(active) : undefined}
        autoComplete="off"
        spellCheck={false}
        className={INPUT}
        value={open ? query : (value ?? '')}
        placeholder={value ?? ''}
        onFocus={openList}
        onClick={() => {
          if (!open) openList();
        }}
        onBlur={close}
        onChange={(event) => {
          setQuery(event.target.value);
          setActive(0);
          setOpen(true);
        }}
        onKeyDown={onKeyDown}
      />
      {open && (
        <ul
          id={listId}
          role="listbox"
          aria-label={label}
          className="absolute top-full left-0 z-20 mt-1 max-h-80 w-64 overflow-y-auto rounded border border-slate-300 bg-white py-1 shadow-lg dark:border-slate-700 dark:bg-slate-900"
        >
          {shown.length === 0 ? (
            <li className="px-2 py-1 text-slate-500">{t('charts.noSymbolMatch')}</li>
          ) : (
            shown.map((o, i) => (
              <li
                key={o.symbol}
                id={optionId(i)}
                role="option"
                aria-selected={o.symbol === value}
                className={`flex cursor-pointer items-center justify-between gap-2 px-2 py-1 ${
                  i === active ? 'bg-slate-200 dark:bg-slate-700' : ''
                } ${o.symbol === value ? 'font-semibold' : ''}`}
                // keep the focus in the input so blur does not close the list before the click lands
                onMouseDown={(event) => {
                  event.preventDefault();
                }}
                onMouseEnter={() => {
                  setActive(i);
                }}
                onClick={() => {
                  choose(o.symbol);
                  inputRef.current?.blur();
                }}
              >
                <span>{o.symbol}</span>
                {o.featured && (
                  <span className="rounded bg-emerald-100 px-1.5 text-xs text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200">
                    {featuredLabel}
                  </span>
                )}
              </li>
            ))
          )}
          {matches.length > shown.length && (
            <li className="px-2 py-1 text-xs text-slate-500">
              {t('charts.moreSymbols', { shown: shown.length, total: matches.length })}
            </li>
          )}
        </ul>
      )}
    </div>
  );
}
