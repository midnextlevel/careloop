const {chromium} = require('playwright');
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({headless: true, channel: process.env.BROWSER_CHANNEL || 'chrome'});
  try {
    const context = await browser.newContext({serviceWorkers: 'block'});
    await context.addCookies([{name: 'sessionid', value: process.env.JOURNAL_BROWSER_SESSION, url: process.env.JOURNAL_BROWSER_URL}]);
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(process.env.JOURNAL_BROWSER_URL);

    for (const fail of [false, true]) {
      const summary = fail ? 'Retain this text after a failed submission.' : 'Submit this reviewed text.';
      await page.getByRole('button', {name: 'Write an entry'}).click();
      await page.getByLabel('Daily summary').fill(summary);
      await page.getByRole('button', {name: 'Review audience'}).click();
      await page.getByRole('checkbox').check();
      let release, received;
      const gate = new Promise(resolve => release = resolve);
      const seen = new Promise(resolve => received = resolve);
      await page.route('**/publish/', async route => {
        received();
        await gate;
        if (fail) await route.abort('failed');
        else await route.continue();
      }, {times: 1});
      try {
        await page.getByRole('button', {name: 'Confirm & submit'}).click();
        await seen;
        const back = page.getByRole('button', {name: 'Back to edit'});
        assert.equal(await back.isDisabled(), true);
        assert.equal(await page.getByRole('button', {name: 'Confirm & submit'}).isDisabled(), true);
        // A disabled button cannot expose the editor even if clicked programmatically.
        await back.evaluate(button => button.click());
        assert.equal(await page.locator('[data-editor]').isVisible(), false);
        release();
        if (fail) {
          await page.getByRole('status').filter({hasText: 'Your text remains in this open page'}).waitFor();
          assert.equal(await back.isEnabled(), true);
          assert.equal(await page.getByRole('button', {name: 'Confirm & submit'}).isEnabled(), true);
          await back.click();
          assert.equal(await page.getByLabel('Daily summary').inputValue(), summary);
          await page.getByLabel('Daily summary').fill('New edits after the failed request are preserved.');
          await page.getByRole('button', {name: 'Review audience'}).click();
          await page.getByRole('checkbox').check();
          await page.getByRole('button', {name: 'Confirm & submit'}).click();
          await page.getByRole('heading', {name: 'School moments'}).waitFor();
          await page.getByText('New edits after the failed request are preserved.', {exact: true}).waitFor();
        } else {
          await page.getByRole('heading', {name: 'School moments'}).waitFor();
          await page.getByText(summary, {exact: true}).waitFor();
        }
      } finally { release(); }
      await page.getByRole('link', {name: 'Back to journal'}).click();
    }
    assert.deepEqual(errors, []);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
