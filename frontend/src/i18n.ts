import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

import translations from './locales/translations.json';

export const SUPPORTED_LANGS = ['ko', 'en', 'ja', 'zh'] as const;
export type Lang = typeof SUPPORTED_LANGS[number];

export const LANG_NATIVE_NAMES: Record<Lang, string> = {
  ko: '한국어',
  en: 'English',
  ja: '日本語',
  zh: '中文',
};

const STORAGE_KEY = 'gemvis.lang';

/**
 * Translation entry = object whose keys are exactly the supported language codes.
 * e.g. { "ko": "설정", "en": "Settings", "ja": "設定", "zh": "设置" }
 */
function isTranslationEntry(obj: unknown): obj is Record<Lang, string> {
  if (typeof obj !== 'object' || obj === null) return false;
  const keys = Object.keys(obj);
  if (keys.length === 0) return false;
  return keys.every((k) => (SUPPORTED_LANGS as readonly string[]).includes(k));
}

/**
 * Walk the multi-language tree and extract a single language's strings.
 * Falls back to ko → en if a particular lang is missing.
 */
function extractLanguage(node: unknown, lang: Lang): unknown {
  if (isTranslationEntry(node)) {
    return node[lang] ?? node.ko ?? node.en ?? '';
  }
  if (typeof node === 'object' && node !== null) {
    const result: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(node)) {
      result[key] = extractLanguage(value, lang);
    }
    return result;
  }
  return node;
}

type ResourceTree = { [key: string]: string | ResourceTree };

function buildResources() {
  const resources: Record<string, { translation: ResourceTree }> = {};
  for (const lang of SUPPORTED_LANGS) {
    resources[lang] = { translation: extractLanguage(translations, lang) as ResourceTree };
  }
  return resources;
}

function detectInitialLang(): Lang {
  const saved = (typeof window !== 'undefined' && window.localStorage.getItem(STORAGE_KEY)) || '';
  if ((SUPPORTED_LANGS as readonly string[]).includes(saved)) return saved as Lang;
  const nav = (typeof navigator !== 'undefined' && navigator.language) || 'ko';
  if (nav.startsWith('en')) return 'en';
  if (nav.startsWith('ja')) return 'ja';
  if (nav.startsWith('zh')) return 'zh';
  return 'ko';
}

const _initialLang = detectInitialLang();

i18n
  .use(initReactI18next)
  .init({
    resources: buildResources(),
    lng: _initialLang,
    fallbackLng: 'ko',
    interpolation: { escapeValue: false },
  });

// Sync the initial language to the backend so the watcher analyzes
// new files in the user's language from the first run.
if (typeof window !== 'undefined') {
  void fetch('/api/preferences', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Accept-Language': _initialLang },
    body: JSON.stringify({ analyze_lang: _initialLang }),
  }).catch(() => { /* silent */ });
}

export function setLanguage(lang: Lang) {
  i18n.changeLanguage(lang);
  try {
    window.localStorage.setItem(STORAGE_KEY, lang);
  } catch { /* ignore */ }
  if (typeof document !== 'undefined') {
    document.documentElement.lang = lang;
  }
  // Tell the backend so the watcher analyzes new files in this language.
  // Fire-and-forget — UI doesn't wait or care about the response.
  void fetch('/api/preferences', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Accept-Language': lang },
    body: JSON.stringify({ analyze_lang: lang }),
  }).catch(() => { /* silent */ });
}

/**
 * Translate a backend API response message.
 * Prefers `message_key` (i18n key) over the legacy `message` field.
 */
export function translateApiMessage(res: {
  message?: string;
  message_key?: string;
  message_params?: Record<string, string | number>;
}): string {
  if (res.message_key) return i18n.t(res.message_key, res.message_params ?? {});
  return res.message ?? '';
}

export default i18n;
