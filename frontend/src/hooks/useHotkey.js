import { useEffect } from 'react';

export const useHotkey = (key, callback, deps = []) => {
  useEffect(() => {
    const handler = (event) => {
      // Проверяем Cmd (Mac) или Ctrl (Windows/Linux)
      const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
      const modifierKey = isMac ? event.metaKey : event.ctrlKey;
      
      if (modifierKey && event.key === key) {
        event.preventDefault();
        callback();
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, deps);
};
