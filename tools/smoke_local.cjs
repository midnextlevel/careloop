// Actual native development login smoke test; credentials are never printed.
const { chromium } = require('playwright');
const fs = require('node:fs');
const assert = require('node:assert/strict');
(async () => {
  const credentials = fs.readFileSync('.local/development-account.txt', 'utf8');
  const username = credentials.match(/^Username: (.+)$/m)[1];
  const password = credentials.match(/^Password: (.+)$/m)[1];
  const browser = await chromium.launch({headless:true, channel:'chrome'});
  try {
    const page = await browser.newPage({viewport:{width:390,height:844}});
    await page.goto('http://127.0.0.1:8000/development/login/');
    await page.getByLabel('Username').fill(username);
    await page.getByLabel('Password').fill(password);
    await page.getByRole('button',{name:'Sign in to test'}).click();
    await page.getByRole('heading',{name:'Day by day'}).waitFor();
    await page.getByRole('button',{name:'Menu', exact:true}).click();
    await page.getByRole('link',{name:'Care team', exact:true}).waitFor();
    await page.keyboard.press('Escape');
    assert.equal(await page.getByRole('button',{name:'Write an entry'}).count(),1);
    if (!await page.getByRole('link',{name:'Read entry'}).count()) {
      await page.locator('[data-dialog-open="date-dialog"]').click();
      await page.getByRole('link',{name:'Show all dates'}).click();
    }
    await page.getByRole('link',{name:'Read entry'}).first().click();
    const entryUrl = page.url();
    await page.getByRole('link',{name:'Back to journal'}).click();
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    if(await page.locator('html').getAttribute('data-theme')!=='dark') await page.locator('[data-theme-toggle]').click();
    assert.equal(await page.locator('html').getAttribute('data-theme'),'dark');
    fs.mkdirSync('test-results',{recursive:true});
    await page.screenshot({path:'test-results/named-account-timeline.png',fullPage:true});
    await page.getByRole('button',{name:'Menu', exact:true}).click();
    await page.getByRole('button',{name:'Sign out'}).click();
    await page.getByRole('heading',{name:'Welcome to Careloop'}).waitFor();
    await page.goto(entryUrl);
    await page.getByRole('heading',{name:'Welcome to Careloop'}).waitFor();
    console.log('PASS: named owner login, owner posting availability, owner controls, dark mode, mobile layout, logout, anonymous denial.');
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exit(1);});
