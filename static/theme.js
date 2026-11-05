// The only persisted UI preference is light/dark; no journal content is stored here.
(() => {
  const system = window.matchMedia('(prefers-color-scheme: dark)');
  const cookie = document.cookie.split(';').map(value => value.trim())
    .find(value => value.startsWith('careloop_theme='))?.split('=')[1];
  let preference = ['light', 'dark'].includes(cookie) ? cookie : null;
  function apply(theme) {
    document.documentElement.dataset.theme = theme;
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', theme === 'dark' ? '#111b18' : '#24594b');
    const toggle = document.querySelector('[data-theme-toggle]');
    if (toggle) {
      toggle.hidden = false;
      toggle.textContent = theme === 'dark' ? 'Light mode' : 'Dark mode';
      toggle.setAttribute('aria-label', theme === 'dark' ? 'Use light mode' : 'Use dark mode');
      toggle.setAttribute('aria-pressed', String(theme === 'dark'));
    }
  }
  apply(preference || (system.matches ? 'dark' : 'light'));
  document.addEventListener('DOMContentLoaded', () => {
    apply(document.documentElement.dataset.theme);
    document.querySelector('[data-theme-toggle]')?.addEventListener('click', () => {
      preference = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
      document.cookie = `careloop_theme=${preference}; Path=/; Max-Age=31536000; SameSite=Lax${location.protocol === 'https:' ? '; Secure' : ''}`;
      apply(preference);
    });
  });
  system.addEventListener('change', () => { if (!preference) apply(system.matches ? 'dark' : 'light'); });
})();
