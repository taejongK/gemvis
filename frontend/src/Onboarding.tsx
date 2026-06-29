import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { api } from './api';
import { SUPPORTED_LANGS, LANG_NATIVE_NAMES, setLanguage, type Lang } from './i18n';
import FolderPicker from './FolderPicker';

interface DirItem {
  path: string;
  enabled: boolean;
}

export default function Onboarding({ onComplete }: { onComplete: () => void }) {
  const { t, i18n } = useTranslation();
  const currentLang = (i18n.resolvedLanguage || i18n.language || 'ko') as Lang;
  const [step, setStep] = useState(0);
  const [dirs, setDirs] = useState<DirItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [analyzeImages, setAnalyzeImages] = useState(true);
  const [showPicker, setShowPicker] = useState(false);

  useEffect(() => {
    if (step === 0) {
      const timer = setTimeout(() => setStep(1), 3000);
      return () => clearTimeout(timer);
    }
  }, [step]);

  useEffect(() => {
    api.watcherStatus().then((s) => {
      const watchSet = new Set(s.watch_dirs);
      const allPaths = new Set([...s.watch_dirs, ...s.default_dirs]);
      const items = Array.from(allPaths)
        .map((p) => ({ path: p, enabled: watchSet.size > 0 ? watchSet.has(p) : true }))
        .sort((a, b) => a.path.localeCompare(b.path));
      setDirs(items);
    }).catch(() => {});
  }, []);

  const handleBegin = async () => {
    setBusy(true);
    setError('');
    try {
      const enabledDirs = dirs.filter((d) => d.enabled).map((d) => d.path);
      await api.updatePreferences({ analyze_images: analyzeImages });
      await api.saveConfig(undefined, enabledDirs);
      onComplete();
    } catch {
      setError(t('onboarding.beginFailed'));
    } finally {
      setBusy(false);
    }
  };

  const toggleDir = (path: string) => {
    setDirs((prev) => prev.map((d) => (d.path === path ? { ...d, enabled: !d.enabled } : d)));
  };

  const removeDir = (path: string) => {
    setDirs((prev) => prev.filter((d) => d.path !== path));
  };


  const TOTAL_STEPS = 3;

  // Step 0: Splash
  if (step === 0) {
    return (
      <div className="onboarding" onClick={() => setStep(1)}>
        <div className="onboarding-splash">
          <div className="hud-ring hud-ring-outer" />
          <div className="hud-ring hud-ring-inner" />
          <img src="/Gemvis_logo_white_v2.png" alt="Gemvis" className="onboarding-splash-logo" />
          <div className="hud-label">G E M V I S</div>
          <svg className="hud-graph" viewBox="0 0 400 400">
            <g className="hud-graph-edges">
              {/* Wave 1: primary branches from ring */}
              <line className="hud-edge e0" x1="185" y1="82" x2="155" y2="25" />
              <line className="hud-edge e1" x1="305" y1="128" x2="355" y2="68" />
              <line className="hud-edge e2" x1="308" y1="275" x2="358" y2="328" />
              <line className="hud-edge e3" x1="112" y1="302" x2="52" y2="350" />
              <line className="hud-edge e4" x1="82" y1="162" x2="26" y2="118" />
              {/* Wave 2: secondary growth */}
              <line className="hud-edge e5" x1="155" y1="25" x2="228" y2="12" />
              <line className="hud-edge e6" x1="355" y1="68" x2="382" y2="125" />
              <line className="hud-edge e7" x1="358" y1="328" x2="382" y2="372" />
              <line className="hud-edge e8" x1="52" y1="350" x2="16" y2="312" />
              <line className="hud-edge e9" x1="52" y1="350" x2="68" y2="388" />
              <line className="hud-edge e10" x1="26" y1="118" x2="18" y2="52" />
              {/* Wave 3: tertiary spread */}
              <line className="hud-edge e11" x1="228" y1="12" x2="278" y2="38" />
              <line className="hud-edge e12" x1="358" y1="328" x2="328" y2="372" />
              <line className="hud-edge e13" x1="26" y1="118" x2="62" y2="75" />
            </g>
            <g className="hud-graph-nodes">
              {/* Wave 1 nodes */}
              <circle className="hud-gnode n0" cx="155" cy="25" r="11" />
              <circle className="hud-gnode n1" cx="355" cy="68" r="9" />
              <circle className="hud-gnode n2" cx="358" cy="328" r="10" />
              <circle className="hud-gnode n3" cx="52" cy="350" r="9" />
              <circle className="hud-gnode n4" cx="26" cy="118" r="10" />
              {/* Wave 2 nodes */}
              <circle className="hud-gnode n5" cx="228" cy="12" r="7" />
              <circle className="hud-gnode n6" cx="382" cy="125" r="5" />
              <circle className="hud-gnode n7" cx="382" cy="372" r="6" />
              <circle className="hud-gnode n8" cx="16" cy="312" r="6" />
              <circle className="hud-gnode n9" cx="68" cy="388" r="5" />
              <circle className="hud-gnode n10" cx="18" cy="52" r="7" />
              {/* Wave 3 nodes */}
              <circle className="hud-gnode n11" cx="278" cy="38" r="4" />
              <circle className="hud-gnode n12" cx="328" cy="372" r="4" />
              <circle className="hud-gnode n13" cx="62" cy="75" r="4" />
            </g>
          </svg>
        </div>
      </div>
    );
  }

  // Step 1: Welcome
  if (step === 1) {
    return (
      <div className="onboarding">
        <div className="onboarding-card">
          <img src="/Gemvis_logo_white_v2.png" alt="Gemvis" className="onboarding-logo" />
          <h1 className="onboarding-title">{t('onboarding.welcomeTitle', { lng: 'en' })}</h1>
          <p className="onboarding-desc">{t('onboarding.welcomeDesc', { lng: 'en' })}</p>
          <div className="onboarding-features">
            <div className="onboarding-feature">
              <span className="onboarding-feature-icon">🔒</span>
              <div>
                <div className="onboarding-feature-title">{t('onboarding.featureLocalTitle', { lng: 'en' })}</div>
                <div className="onboarding-feature-desc">{t('onboarding.featureLocalDesc', { lng: 'en' })}</div>
              </div>
            </div>
            <div className="onboarding-feature">
              <span className="onboarding-feature-icon">◈</span>
              <div>
                <div className="onboarding-feature-title">{t('onboarding.featureGraphTitle', { lng: 'en' })}</div>
                <div className="onboarding-feature-desc">{t('onboarding.featureGraphDesc', { lng: 'en' })}</div>
              </div>
            </div>
            <div className="onboarding-feature">
              <span className="onboarding-feature-icon">✦</span>
              <div>
                <div className="onboarding-feature-title">{t('onboarding.featureSearchTitle', { lng: 'en' })}</div>
                <div className="onboarding-feature-desc">{t('onboarding.featureSearchDesc', { lng: 'en' })}</div>
              </div>
            </div>
          </div>
          <div className="onboarding-actions">
            <button className="btn btn-primary" onClick={() => setStep(2)}>
              {t('onboarding.start', { lng: 'en' })}
            </button>
            <button className="btn btn-ghost" onClick={onComplete}>
              {t('onboarding.skip', { lng: 'en' })}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Step 2: Language
  if (step === 2) {
    return (
      <div className="onboarding">
        <div className="onboarding-card">
          <div className="onboarding-step-badge">
            {t('onboarding.stepIndicator', { current: 1, total: TOTAL_STEPS })}
          </div>
          <h2 className="onboarding-title">{t('onboarding.langTitle')}</h2>
          <p className="onboarding-desc">{t('onboarding.langDesc')}</p>
          <div className="settings-chip-row onboarding-chips">
            {SUPPORTED_LANGS.map((code) => (
              <button
                key={code}
                type="button"
                className={`settings-chip${currentLang === code ? ' active' : ''}`}
                onClick={() => setLanguage(code)}
              >
                {LANG_NATIVE_NAMES[code]}
              </button>
            ))}
          </div>
          <div className="onboarding-actions">
            <button className="btn btn-primary" onClick={() => setStep(3)}>
              {t('onboarding.next')}
            </button>
            <button className="btn btn-ghost" onClick={() => setStep(1)}>
              {t('onboarding.back')}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Step 3: Image Analysis Option
  if (step === 3) {
    return (
      <div className="onboarding">
        <div className="onboarding-card">
          <div className="onboarding-step-badge">
            {t('onboarding.stepIndicator', { current: 2, total: TOTAL_STEPS })}
          </div>
          <h2 className="onboarding-title">{t('onboarding.imageTitle')}</h2>
          <p className="onboarding-desc">{t('onboarding.imageDesc')}</p>
          <div className="onboarding-image-options">
            <button
              type="button"
              className={`onboarding-image-option${analyzeImages ? ' selected' : ''}`}
              onClick={() => setAnalyzeImages(true)}
            >
              <span className="onboarding-image-option-icon">🖼️</span>
              <div className="onboarding-image-option-title">{t('onboarding.imageOptionOn')}</div>
              <div className="onboarding-image-option-desc">{t('onboarding.imageOptionOnDesc')}</div>
            </button>
            <button
              type="button"
              className={`onboarding-image-option${!analyzeImages ? ' selected' : ''}`}
              onClick={() => setAnalyzeImages(false)}
            >
              <span className="onboarding-image-option-icon">⚡</span>
              <div className="onboarding-image-option-title">{t('onboarding.imageOptionOff')}</div>
              <div className="onboarding-image-option-desc">{t('onboarding.imageOptionOffDesc')}</div>
            </button>
          </div>
          <div className="onboarding-actions">
            <button className="btn btn-primary" onClick={() => setStep(4)}>
              {t('onboarding.next')}
            </button>
            <button className="btn btn-ghost" onClick={() => setStep(2)}>
              {t('onboarding.back')}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Step 4: Watch Folders
  return (
    <div className="onboarding">
      <div className="onboarding-card">
        <div className="onboarding-step-badge">
          {t('onboarding.stepIndicator', { current: 3, total: TOTAL_STEPS })}
        </div>
        <h2 className="onboarding-title">{t('onboarding.dirsTitle')}</h2>
        <p className="onboarding-desc">{t('onboarding.dirsDesc')}</p>
        <div className="onboarding-dirs">
          {dirs.map((d) => (
            <div key={d.path} className="onboarding-dir-row">
              <label className="onboarding-dir-check">
                <input
                  type="checkbox"
                  checked={d.enabled}
                  onChange={() => toggleDir(d.path)}
                />
                <code>{d.path}</code>
              </label>
              <button
                type="button"
                className="onboarding-dir-remove"
                onClick={() => removeDir(d.path)}
                aria-label={t('settings.dirRemove')}
              >
                ×
              </button>
            </div>
          ))}
          <button className="btn" onClick={() => setShowPicker(true)}>
            + {t('settings.dirAdd')}
          </button>
        </div>
        {error && <div className="onboarding-error">{error}</div>}
        <div className="onboarding-actions">
          <button className="btn btn-primary" disabled={busy} onClick={handleBegin}>
            {busy ? '...' : t('onboarding.begin')}
          </button>
          <button className="btn btn-ghost" disabled={busy} onClick={() => setStep(3)}>
            {t('onboarding.back')}
          </button>
        </div>
        <FolderPicker
          open={showPicker}
          onSelect={(path) => {
            setShowPicker(false);
            if (!dirs.some((d) => d.path === path)) {
              setDirs((prev) => [...prev, { path, enabled: true }]);
            }
          }}
          onCancel={() => setShowPicker(false)}
        />
      </div>
    </div>
  );
}
