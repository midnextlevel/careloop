const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
(async () => {
  const browser = await chromium.launch({headless:true, channel:process.env.BROWSER_CHANNEL || 'chrome'});
  try {
    const contexts = {};
    for (const role of ['OWNER','TEACHER','THERAPIST']) {
      contexts[role] = await browser.newContext({viewport:{width:390,height:844}});
      await contexts[role].addCookies([{name:'sessionid', value:process.env[role + '_SESSION'], url:process.env.JOURNAL_BROWSER_URL}]);
    }
    const page = await contexts.OWNER.newPage();
    const entryUrl = process.env.JOURNAL_BROWSER_URL + '/entries/' + process.env.ENTRY_ID + '/';
    await page.goto(process.env.JOURNAL_BROWSER_URL + '/access/');
    await page.getByLabel('Fixed access deadline').fill(process.env.ACCESS_UNTIL);
    await page.getByLabel('Also expire access').check();
    await page.getByRole('button', {name:'Save access settings'}).click();
    for (const role of ['TEACHER','THERAPIST']) assert.equal((await contexts[role].request.get(entryUrl)).status(), 200);
    await page.getByLabel('Fixed access deadline').fill('2000-01-01T00:00');
    await page.getByRole('button', {name:'Save access settings'}).click();
    for (const role of ['TEACHER','THERAPIST']) assert.equal((await contexts[role].request.get(entryUrl)).status(), 404);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    fs.mkdirSync('test-results', {recursive:true});
    await page.screenshot({path:'test-results/owner-data-access.png', fullPage:true});
    await page.goto(entryUrl);
    await page.getByRole('button', {name:'Manage entry access'}).click();
    await page.getByLabel('Allow professional access until').fill(process.env.ACCESS_UNTIL);
    await page.getByRole('button', {name:'Save entry access'}).click();
    for (const role of ['TEACHER','THERAPIST']) assert.equal((await contexts[role].request.get(entryUrl)).status(), 200);
    await page.getByRole('button', {name:'Manage entry access'}).click();
    await page.getByRole('button', {name:'Hide now'}).click();
    for (const role of ['TEACHER','THERAPIST']) assert.equal((await contexts[role].request.get(entryUrl)).status(), 404);
    assert.equal((await contexts.OWNER.request.get(entryUrl)).status(), 200);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
