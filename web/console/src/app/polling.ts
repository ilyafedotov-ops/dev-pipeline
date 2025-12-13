import React from 'react';

import { useSettingsSnapshot } from '@/app/settings/store';

export function useDocumentVisible(): boolean {
  const [visible, setVisible] = React.useState(() => (typeof document === 'undefined' ? true : !document.hidden));
  React.useEffect(() => {
    const onChange = () => setVisible(!document.hidden);
    document.addEventListener('visibilitychange', onChange);
    return () => document.removeEventListener('visibilitychange', onChange);
  }, []);
  return visible;
}

export function useEffectivePollingInterval(defaultMs: number): number | false {
  const settings = useSettingsSnapshot();
  const visible = useDocumentVisible();
  if (!settings.polling.enabled) return false;
  if (settings.polling.disableInBackground && !visible) return false;
  return defaultMs;
}

