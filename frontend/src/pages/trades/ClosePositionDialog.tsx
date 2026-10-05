import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { EngineCodeField } from '@/components/EngineCodeField';
import { StepUpDialog } from '@/components/StepUpDialog';
import { commandKeys, ENGINE_CODE, postCommand } from '@/engine/commands';

/** POSITION_CLOSE for one of the bot's positions: step-up plus the engine's control code (TAA-911). */
export function ClosePositionDialog({
  engineId,
  ticket,
  label,
  onClose,
}: {
  engineId: string;
  ticket: number;
  label: string;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [code, setCode] = useState('');
  return (
    <StepUpDialog
      title={t('controls.close.title', { position: label })}
      confirmLabel={t('controls.close.confirm')}
      danger
      validate={() => (ENGINE_CODE.test(code) ? null : t('controls.engineCodeRequired'))}
      onConfirm={async () => {
        await postCommand(engineId, { type: 'POSITION_CLOSE', ticket, code });
        await queryClient.invalidateQueries({ queryKey: commandKeys.all(engineId) });
      }}
      onClose={onClose}
    >
      <p>{t('controls.close.body')}</p>
      <EngineCodeField value={code} onChange={setCode} />
    </StepUpDialog>
  );
}
