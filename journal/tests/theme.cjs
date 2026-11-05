const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
(async () => {
  const browser = await chromium.launch({headless:true, channel:process.env.BROWSER_CHANNEL || 'chrome'});
  try {
    const context = await browser.newContext({viewport:{width:390,height:844}, colorScheme:'dark'});
    await context.addCookies([{name:'sessionid', value:process.env.JOURNAL_BROWSER_SESSION, url:process.env.JOURNAL_BROWSER_URL}]);
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(process.env.JOURNAL_BROWSER_URL);
    assert.equal(await page.locator('html').getAttribute('data-theme'), 'dark');
    assert.equal(await page.getByRole('button', {name:'Write an entry'}).count(), 1);
    assert.equal(await page.getByRole('heading', {name:'Your drafts'}).count(), 0);
    assert.equal(await page.evaluate(() => getComputedStyle(document.body).backgroundColor), 'rgb(17, 27, 24)');
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    for (const width of [320, 360, 390, 430, 768, 1280]) {
      await page.setViewportSize({width, height:844});
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `Overflow at ${width}px`);
      assert.ok(await page.locator('.top').evaluate(el => el.getBoundingClientRect().height <= 80), `Header wraps at ${width}px`);
      assert.equal(await page.locator('.brand-logo').evaluate(el => el.complete && el.naturalWidth > 0), true);
      for (const control of ['.theme-toggle', '.menu-trigger', '.date-trigger', '.icon-button', '.toolbar-actions button']) {
        for (const box of await page.locator(control).evaluateAll(nodes => nodes.map(el => el.getBoundingClientRect().toJSON()))) {
          assert.ok(box.width >= 44 && box.height >= 44, `${control} is too small at ${width}px`);
        }
      }
    }
    await page.setViewportSize({width:390,height:844});
    assert.ok(await page.locator('.compact-timeline').evaluate(el => el.getBoundingClientRect().top < 400));
    assert.equal(await page.locator('#access-info-dialog').isVisible(), false);
    await page.getByRole('button', {name:'Menu',exact:true}).click();
    await page.getByRole('link', {name:'Care team',exact:true}).waitFor();
    await page.screenshot({path:'test-results/mobile-navigation-menu.png'});
    await page.getByRole('button', {name:'Access info'}).click();
    assert.equal(await page.locator('#access-info-dialog').isVisible(), true);
    await page.keyboard.press('Escape');
    assert.equal(await page.locator('#access-info-dialog').isVisible(), false);
    assert.equal(await page.getByRole('button', {name:'Access info'}).evaluate(el => el === document.activeElement), true);
    await page.keyboard.press('Escape');
    assert.equal(await page.getByRole('button', {name:'Menu',exact:true}).evaluate(el => el === document.activeElement), true);
    fs.mkdirSync('test-results', {recursive:true});
    await page.screenshot({path:'test-results/owner-dark-mode.png', fullPage:true});
    await page.getByRole('button', {name:'Use light mode'}).click();
    assert.equal(await page.locator('html').getAttribute('data-theme'), 'light');
    await page.reload();
    assert.equal(await page.locator('html').getAttribute('data-theme'), 'light');
    await page.getByRole('button', {name:'Use dark mode'}).click();
    await page.getByRole('button', {name:'Menu',exact:true}).click();
    await page.getByRole('link', {name:'Data access',exact:true}).click();
    assert.equal(await page.locator('html').getAttribute('data-theme'), 'dark');
    assert.equal(await page.getByLabel('Days of access after submission').evaluate(el => getComputedStyle(el).backgroundColor), 'rgb(20, 35, 27)');
    assert.equal(await page.evaluate(() => localStorage.length), 0);
    assert.equal((await context.cookies()).find(cookie => cookie.name === 'careloop_theme').value, 'dark');
    await page.setViewportSize({width:1280,height:900});
    await page.screenshot({path:'test-results/access-dark-mode.png', fullPage:true});
    assert.deepEqual(errors, []);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
