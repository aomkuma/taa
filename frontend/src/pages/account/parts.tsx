import { useTranslation } from 'react-i18next';

/** A plan's name in the UI language (seeded plans); another plan shows its code. */
export function PlanName({ code }: { code: string }) {
  const { t, i18n } = useTranslation();
  return <>{i18n.exists(`account.planName.${code}`) ? t(`account.planName.${code as 'FREE'}`) : code}</>;
}
