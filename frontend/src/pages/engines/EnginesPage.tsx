import { useQuery, useQueryClient } from '@tanstack/react-query';
import { type ReactNode, useId, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { z } from 'zod';

import { ApiError, apiGet, apiPost, apiPostEmpty } from '@/api/client';
import { useServerNow } from '@/app/useNow';
import { StepUpDialog } from '@/components/StepUpDialog';
import { ENGINES_QUERY_KEY, type EngineSummary, EngineListSchema } from '@/engine/schemas';
import { translateCode } from '@/i18n/codes';
import { useFormat } from '@/i18n/useFormat';
import { Card } from '@/pages/dashboard/cards';

import { type EngineBadge, engineBadge, envBlock, keyAgeDays } from './engineModel';
import { QrCode } from './QrCode';
import { newSecret, provisioningUri, verifyCode } from './totp';

const BUTTON =
  'rounded border border-slate-300 px-3 py-1 text-sm hover:bg-slate-100 disabled:opacity-50 dark:border-slate-700 dark:hover:bg-slate-800';
const PRIMARY =
  'rounded bg-sky-700 px-3 py-1 text-sm font-medium text-white hover:bg-sky-800 disabled:opacity-50';
const INPUT =
  'rounded border border-slate-300 bg-white px-2 py-1 text-sm dark:border-slate-700 dark:bg-slate-950';
const BADGES: Record<EngineBadge, string> = {
  waiting: 'bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-200',
  connected: 'bg-emerald-100 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-200',
  offline: 'bg-red-100 text-red-900 dark:bg-red-900/40 dark:text-red-200',
  revoked: 'bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
};
/** While a new engine waits for its first contact, the list is polled this often. */
const WAITING_POLL_MS = 5_000;

/** `POST /engines` and `/engines/{id}/rotate`: the secret is in this one response only (`no-store`). */
const IssuedSchema = z.object({
  engine_id: z.string(),
  secret: z.string(),
  cloud_base_url: z.string().optional(),
});
type Issued = z.infer<typeof IssuedSchema>;

/** An engine API error in words (`codes:engine.<code>`), or null for the dialog's default text. */
function useEngineError() {
  const { i18n } = useTranslation();
  return (err: unknown): string | null =>
    err instanceof ApiError && err.code !== 'step_up_required'
      ? translateCode(i18n, 'engine', err.code)
      : null;
}

/** The `.env` lines with copy and download; the text exists only in this component's props. */
function EnvBox({ text, fileName }: { text: string; fileName: string }) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);
  return (
    <div className="space-y-2">
      <pre className="overflow-x-auto rounded bg-slate-900 p-3 text-xs text-slate-100">{text}</pre>
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          className={BUTTON}
          onClick={() => {
            void navigator.clipboard.writeText(text).then(() => {
              setCopied(true);
            });
          }}
        >
          {t('engines.env.copy')}
        </button>
        <button
          type="button"
          className={BUTTON}
          onClick={() => {
            const url = URL.createObjectURL(new Blob([text], { type: 'text/plain' }));
            const link = document.createElement('a');
            link.href = url;
            link.download = fileName;
            link.click();
            URL.revokeObjectURL(url);
          }}
        >
          {t('engines.env.download')}
        </button>
        {copied && (
          <span role="status" className="text-sm text-slate-600 dark:text-slate-400">
            {t('engines.env.copied')}
          </span>
        )}
      </div>
      <p className="text-xs text-slate-500">{t('engines.env.keyring')}</p>
    </div>
  );
}

/** A new CONTROL_TOTP_SECRET: made here, scanned, confirmed with one code here; never sent anywhere. */
function ControlTotp({ label, onConfirmed }: { label: string; onConfirmed: (secret: string) => void }) {
  const { t } = useTranslation();
  const id = useId();
  const [secret] = useState(newSecret);
  const [code, setCode] = useState('');
  const [result, setResult] = useState<'ok' | 'bad' | null>(null);
  return (
    <div className="space-y-2 text-sm">
      <p>{t('engines.totp.intro')}</p>
      <div className="flex flex-wrap items-start gap-4">
        <QrCode value={provisioningUri(secret, label)} label={t('engines.totp.qr')} />
        <div className="space-y-2">
          <p className="text-xs">
            {t('engines.totp.manual')} <code className="break-all">{secret}</code>
          </p>
          <label htmlFor={id} className="block font-medium">
            {t('engines.totp.code')}
          </label>
          <div className="flex gap-2">
            <input
              id={id}
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              className={`${INPUT} w-28 tracking-widest`}
              value={code}
              onChange={(e) => {
                setResult(null);
                setCode(e.target.value.replace(/\D/g, ''));
              }}
            />
            <button
              type="button"
              className={BUTTON}
              disabled={code.length !== 6 || result === 'ok'}
              onClick={() => {
                void verifyCode(secret, code, Date.now() / 1000).then((ok) => {
                  setResult(ok ? 'ok' : 'bad');
                  if (ok) onConfirmed(secret);
                });
              }}
            >
              {t('engines.totp.check')}
            </button>
          </div>
          {result === 'ok' && (
            <p role="status" className="text-emerald-700 dark:text-emerald-400">
              {t('engines.totp.ok')}
            </p>
          )}
          {result === 'bad' && (
            <p role="alert" className="text-red-700 dark:text-red-400">
              {t('engines.totp.bad')}
            </p>
          )}
        </div>
      </div>
      <p className="text-xs text-slate-500">{t('engines.totp.never')}</p>
    </div>
  );
}

function Checklist() {
  const { t } = useTranslation();
  const steps = ['terminal', 'password', 'algo', 'env', 'doctor', 'start'] as const;
  return (
    <ol className="list-decimal space-y-1 pl-5 text-sm">
      {steps.map((s) => (
        <li key={s}>{t(`engines.checklist.${s}`)}</li>
      ))}
    </ol>
  );
}

function Step({ n, title, children }: { n: number; title: string; children: ReactNode }) {
  return (
    <section aria-label={title} className="space-y-2 border-t border-slate-200 pt-3 dark:border-slate-800">
      <h3 className="font-medium">
        {n}. {title}
      </h3>
      {children}
    </section>
  );
}

/** The add wizard after the server issued the keys: secrets in this component's state only. */
function NewEngine({
  issued,
  label,
  engine,
  onDone,
}: {
  issued: Issued;
  label: string;
  engine: EngineSummary | undefined;
  onDone: () => void;
}) {
  const { t } = useTranslation();
  const [totp, setTotp] = useState<string | null>(null);
  const connected = engine?.first_seen_at != null;
  return (
    <Card title={t('engines.add.title', { label })}>
      <div className="space-y-4">
        <Step n={1} title={t('engines.add.keysTitle')}>
          <p role="alert" className="text-sm text-amber-800 dark:text-amber-300">
            {t('engines.add.once')}
          </p>
          <dl className="text-sm">
            <dt className="text-xs text-slate-500">ENGINE_ID</dt>
            <dd className="font-mono break-all">{issued.engine_id}</dd>
            <dt className="mt-1 text-xs text-slate-500">ENGINE_HMAC_SECRET</dt>
            <dd className="font-mono break-all">{issued.secret}</dd>
          </dl>
        </Step>
        <Step n={2} title={t('engines.totp.title')}>
          <ControlTotp label={label} onConfirmed={setTotp} />
        </Step>
        <Step n={3} title={t('engines.env.title')}>
          {totp === null && <p className="text-sm text-slate-500">{t('engines.env.afterTotp')}</p>}
          <EnvBox
            text={envBlock({
              cloudBaseUrl: issued.cloud_base_url,
              engineId: issued.engine_id,
              hmacSecret: issued.secret,
              controlTotp: totp ?? undefined,
            })}
            fileName=".env.engine"
          />
        </Step>
        <Step n={4} title={t('engines.checklist.title')}>
          <Checklist />
        </Step>
        <Step n={5} title={t('engines.add.contactTitle')}>
          <p role="status" className="text-sm">
            {connected ? t('engines.add.connected') : t('engines.add.waiting')}
          </p>
        </Step>
        <button type="button" className={PRIMARY} onClick={onDone}>
          {t('engines.add.done')}
        </button>
      </div>
    </Card>
  );
}

function AddCard({ onIssued }: { onIssued: (issued: Issued, label: string) => void }) {
  const { t } = useTranslation();
  const id = useId();
  const engineError = useEngineError();
  const [label, setLabel] = useState('');
  const [confirming, setConfirming] = useState(false);
  const trimmed = label.trim();
  return (
    <Card title={t('engines.add.newTitle')}>
      <div className="space-y-2 text-sm">
        <p className="text-slate-600 dark:text-slate-400">{t('engines.add.notice')}</p>
        <label htmlFor={id} className="block font-medium">
          {t('engines.add.label')}
        </label>
        <div className="flex flex-wrap gap-2">
          <input
            id={id}
            className={`${INPUT} w-64`}
            maxLength={64}
            value={label}
            placeholder={t('engines.add.labelHint')}
            onChange={(e) => {
              setLabel(e.target.value);
            }}
          />
          <button
            type="button"
            className={PRIMARY}
            disabled={trimmed === ''}
            onClick={() => {
              setConfirming(true);
            }}
          >
            {t('engines.add.create')}
          </button>
        </div>
      </div>
      {confirming && (
        <StepUpDialog
          title={t('engines.add.confirmTitle')}
          confirmLabel={t('engines.add.create')}
          errorText={engineError}
          onConfirm={async () => {
            const issued = await apiPost('/engines', { label: trimmed }, IssuedSchema);
            onIssued(issued, trimmed);
            setLabel('');
          }}
          onClose={() => {
            setConfirming(false);
          }}
        >
          <p>{t('engines.add.confirmBody', { label: trimmed })}</p>
        </StepUpDialog>
      )}
    </Card>
  );
}

type Action = { kind: 'rotate' | 'revoke' | 'totp'; engine: EngineSummary };

function RevokeDialog({ engine, onClose }: { engine: EngineSummary; onClose: () => void }) {
  const { t } = useTranslation();
  const id = useId();
  const queryClient = useQueryClient();
  const engineError = useEngineError();
  const [typed, setTyped] = useState('');
  return (
    <StepUpDialog
      title={t('engines.revoke.title')}
      confirmLabel={t('engines.revoke.button')}
      danger
      errorText={engineError}
      validate={() => (typed === engine.engine_id ? null : t('engines.revoke.mismatch'))}
      onConfirm={async () => {
        await apiPostEmpty(`/engines/${encodeURIComponent(engine.engine_id)}/revoke`, { confirm: typed });
        await queryClient.invalidateQueries({ queryKey: ENGINES_QUERY_KEY });
      }}
      onClose={onClose}
    >
      <p>{t('engines.revoke.body', { label: engine.label })}</p>
      <label htmlFor={id} className="mt-2 block text-sm font-medium">
        {t('engines.revoke.type', { id: engine.engine_id })}
      </label>
      <input
        id={id}
        className={`${INPUT} mt-1 w-full font-mono`}
        value={typed}
        onChange={(e) => {
          setTyped(e.target.value.trim());
        }}
      />
    </StepUpDialog>
  );
}

function EngineRow({
  engine,
  now,
  onAction,
}: {
  engine: EngineSummary;
  now: number;
  onAction: (action: Action) => void;
}) {
  const { t } = useTranslation();
  const format = useFormat();
  const badge = engineBadge(engine, now);
  const age = keyAgeDays(engine, now);
  const active = engine.status !== 'REVOKED';
  return (
    <li className="space-y-1 py-2">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">{engine.label}</span>
        <span className={`rounded px-1.5 py-0.5 text-xs ${BADGES[badge]}`}>
          {t(`engines.badge.${badge}`)}
        </span>
        {engine.rotation_pending === true && (
          <span className="text-xs text-amber-800 dark:text-amber-300">{t('engines.rotationPending')}</span>
        )}
      </div>
      <p className="font-mono text-xs break-all text-slate-500">{engine.engine_id}</p>
      <p className="text-xs text-slate-600 dark:text-slate-400">
        {t('engines.lastSeen', {
          at: engine.last_seen_at ? format.dateTime(engine.last_seen_at) : t('engines.never'),
        })}
        {age !== null && ` · ${t('engines.keyAge', { n: age })}`}
      </p>
      {active && (
        <div className="flex flex-wrap gap-2">
          {(['rotate', 'totp', 'revoke'] as const).map((kind) => (
            <button
              key={kind}
              type="button"
              className={`${BUTTON} ${kind === 'revoke' ? 'text-red-700 dark:text-red-400' : ''}`}
              onClick={() => {
                onAction({ kind, engine });
              }}
            >
              {t(`engines.action.${kind}`)}
            </button>
          ))}
        </div>
      )}
    </li>
  );
}

/**
 * PLAN §A32 "เชื่อมต่อ Engine / Engines" (TAA-923): the user's engines with status and key age; the add wizard
 * (server-issued id and HMAC secret shown once, the control TOTP made and checked in the browser, the `.env`
 * block and the Windows checklist), rotation, revocation and a new control TOTP. Secrets live only in this
 * page's component state: never in the query cache, storage or the service worker.
 */
export function EnginesPage() {
  const { t } = useTranslation();
  const now = useServerNow(30_000);
  const queryClient = useQueryClient();
  const engineError = useEngineError();
  const [created, setCreated] = useState<{ issued: Issued; label: string } | null>(null);
  const [rotated, setRotated] = useState<{ issued: Issued; engine: EngineSummary } | null>(null);
  const [action, setAction] = useState<Action | null>(null);
  const list = useQuery({
    queryKey: ENGINES_QUERY_KEY,
    queryFn: ({ signal }) => apiGet('/engines', EngineListSchema, { signal }),
    refetchInterval: created !== null ? WAITING_POLL_MS : false,
  });
  const engines = list.data?.items ?? [];
  const refresh = () => queryClient.invalidateQueries({ queryKey: ENGINES_QUERY_KEY });
  return (
    <section>
      <h1 className="mb-2 text-2xl font-semibold">{t('nav.engines')}</h1>
      <p className="mb-4 text-sm text-slate-600 dark:text-slate-400">{t('engines.intro')}</p>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title={t('engines.list.title')}>
          {list.data === undefined ? (
            <p className="text-sm text-slate-500">
              {list.isError ? t('dashboard.loadFailed') : t('dashboard.loading')}
            </p>
          ) : engines.length === 0 ? (
            <p className="text-sm text-slate-500">{t('engines.list.none')}</p>
          ) : (
            <ul className="divide-y divide-slate-200 dark:divide-slate-800">
              {engines.map((engine) => (
                <EngineRow key={engine.engine_id} engine={engine} now={now} onAction={setAction} />
              ))}
            </ul>
          )}
        </Card>
        <div className="flex flex-col gap-4">
          {created !== null ? (
            <NewEngine
              issued={created.issued}
              label={created.label}
              engine={engines.find((e) => e.engine_id === created.issued.engine_id)}
              onDone={() => {
                setCreated(null);
              }}
            />
          ) : (
            <AddCard
              onIssued={(issued, label) => {
                setCreated({ issued, label });
                void refresh();
              }}
            />
          )}
          {rotated !== null && (
            <Card title={t('engines.rotate.doneTitle', { label: rotated.engine.label })}>
              <p role="alert" className="mb-2 text-sm text-amber-800 dark:text-amber-300">
                {t('engines.rotate.once')}
              </p>
              <EnvBox
                text={envBlock({ engineId: rotated.issued.engine_id, hmacSecret: rotated.issued.secret })}
                fileName=".env.engine"
              />
              <p className="mt-2 text-xs text-slate-500">{t('engines.rotate.restart')}</p>
              <button
                type="button"
                className={`${BUTTON} mt-2`}
                onClick={() => {
                  setRotated(null);
                }}
              >
                {t('engines.add.done')}
              </button>
            </Card>
          )}
          {action?.kind === 'totp' && (
            <Card title={t('engines.totp.newTitle', { label: action.engine.label })}>
              <ControlTotpPanel
                engine={action.engine}
                onClose={() => {
                  setAction(null);
                }}
              />
            </Card>
          )}
        </div>
      </div>
      {action?.kind === 'rotate' && (
        <StepUpDialog
          title={t('engines.rotate.title')}
          confirmLabel={t('engines.rotate.button')}
          errorText={engineError}
          onConfirm={async () => {
            const issued = await apiPost(
              `/engines/${encodeURIComponent(action.engine.engine_id)}/rotate`,
              undefined,
              IssuedSchema,
            );
            setRotated({ issued, engine: action.engine });
            await refresh();
          }}
          onClose={() => {
            setAction(null);
          }}
        >
          <p>{t('engines.rotate.body', { label: action.engine.label })}</p>
        </StepUpDialog>
      )}
      {action?.kind === 'revoke' && (
        <RevokeDialog
          engine={action.engine}
          onClose={() => {
            setAction(null);
          }}
        />
      )}
    </section>
  );
}

/** A new control TOTP for an existing engine: browser only, then the line to change and a restart. */
function ControlTotpPanel({ engine, onClose }: { engine: EngineSummary; onClose: () => void }) {
  const { t } = useTranslation();
  const [secret, setSecret] = useState<string | null>(null);
  return (
    <div className="space-y-3">
      <ControlTotp label={engine.label} onConfirmed={setSecret} />
      {secret !== null && (
        <>
          <EnvBox text={`CONTROL_TOTP_SECRET=${secret}\n`} fileName=".env.control" />
          <p className="text-xs text-slate-500">{t('engines.totp.restart')}</p>
        </>
      )}
      <button type="button" className={BUTTON} onClick={onClose}>
        {t('engines.add.done')}
      </button>
    </div>
  );
}
