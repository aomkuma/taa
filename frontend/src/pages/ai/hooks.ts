import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';

import { apiGet } from '@/api/client';
import { useEngine } from '@/engine/context';

import { type AINote, type AINoteKind, AINotesSchema, aiNoteKeys } from './schemas';

/** The latest AI notes of one kind (null while loading, on error or without the plan's AI feature). */
export function useAINotes(kind: AINoteKind, days = 30) {
  const { engineId } = useEngine();
  const id = engineId ?? '';
  return useQuery({
    queryKey: aiNoteKeys.list(id, kind, days),
    queryFn: ({ signal }) =>
      apiGet(`/engines/${encodeURIComponent(id)}/ai-notes?kind=${kind}&days=${String(days)}`, AINotesSchema, {
        signal,
      }),
    enabled: engineId !== null,
    retry: false, // 403 without the plan's AI feature: show nothing
  });
}

/** The note's text in the UI language (the other language when one is empty). */
export function useNoteText(note: AINote): string {
  const { i18n } = useTranslation();
  const th = i18n.language.startsWith('th');
  return (th ? note.text_th : note.text_en) || note.text_en || note.text_th;
}
