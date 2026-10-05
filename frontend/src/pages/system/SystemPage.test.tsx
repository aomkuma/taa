import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { apiError, type Handler, json } from '@/test/api';
import { owner, renderShell } from '@/test/engine';
import samples from '@/test/fixtures/api-samples.json';

const STATUS = samples['engines/ENGINE/status'];
const CONFIG = samples['engines/ENGINE/config'];
const VERIFY = samples['engines/ENGINE/audit/verify'];

function setup(extra: Record<string, Handler> = {}) {
  return owner({
    'GET /engines/e1/status': () => json(STATUS),
    'GET /engines/e1/config': () => json(CONFIG),
    ...extra,
  });
}

const card = (name: string) => screen.findByRole('region', { name });

describe('system page', () => {
  it('shows engine health, sync and the masked terminal and account', async () => {
    setup();
    renderShell('/system');
    const engine = await card('Engine and connection');
    expect(within(engine).getByText('alice pc')).toBeInTheDocument();
    expect(within(engine).getByText('PAPER · RUNNING')).toBeInTheDocument();
    expect(within(engine).getByText('Online')).toBeInTheDocument();
    const sync = await card('Sync');
    expect(within(sync).getByText('1 s')).toBeInTheDocument(); // received one second after it was sent
    expect(within(sync).getByText('Waiting to upload').nextElementSibling).toHaveTextContent('0');
    const account = await card('Terminal and account');
    expect(await within(account).findByText('*****678')).toBeInTheDocument();
    expect(within(account).getByText('FBS-Demo')).toBeInTheDocument();
    expect(within(account).queryByText('investor-pass')).not.toBeInTheDocument();
  });

  it('verifies the audit chain on request', async () => {
    const api = setup({ 'GET /engines/e1/audit/verify': () => json(VERIFY) });
    const user = userEvent.setup();
    renderShell('/system');
    const audit = await card('Audit chain');
    expect(within(audit).getByText('intact')).toBeInTheDocument();
    expect(within(audit).getByText('3 / 3')).toBeInTheDocument();
    await user.click(within(audit).getByRole('button', { name: 'Verify now' }));
    expect(await within(audit).findByRole('status')).toHaveTextContent(
      'The chain is intact (3 events checked).',
    );
    expect(api.calls.map((c) => c.path)).toContain('/engines/e1/audit/verify');
  });

  it('reports a broken chain', async () => {
    setup({
      'GET /engines/e1/audit/verify': () =>
        json({ ...VERIFY, ok: false, first_bad_seq: 2, detail: 'hash mismatch at seq 2' }),
    });
    const user = userEvent.setup();
    renderShell('/system');
    const audit = await card('Audit chain');
    await user.click(within(audit).getByRole('button', { name: 'Verify now' }));
    expect(await within(audit).findByRole('status')).toHaveTextContent(
      'The chain breaks at 2: hash mismatch at seq 2',
    );
  });

  it('says when the configuration cannot be read', async () => {
    setup({ 'GET /engines/e1/config': () => apiError(404, 'config_not_found') });
    renderShell('/system');
    const account = await card('Terminal and account');
    expect(await within(account).findByText('Could not load this data.')).toBeInTheDocument();
  });
});
