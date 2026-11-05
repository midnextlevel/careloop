const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
(async () => {
  const browser = await chromium.launch({headless:true, channel:process.env.BROWSER_CHANNEL || 'chrome'});
  try {
    const context = await browser.newContext({viewport:{width:390,height:844}});
    await context.addCookies([{name:'sessionid',value:process.env.JOURNAL_BROWSER_SESSION,url:process.env.JOURNAL_BROWSER_URL}]);
    const page = await context.newPage();
    await page.goto(process.env.JOURNAL_BROWSER_URL);
    await page.getByRole('button',{name:'Write an entry'}).click();
    assert.equal(await page.getByLabel('Entry type').inputValue(), 'home');
    await page.getByLabel('Daily summary').fill('A parent observation with two optional photos.');
    const buffer = Buffer.from(process.env.PHOTO_BASE64,'base64');
    await page.getByLabel('Add photos').setInputFiles([{name:'one.jpg',mimeType:'image/jpeg',buffer},{name:'two.jpg',mimeType:'image/jpeg',buffer}]);
    await context.setOffline(true);
    await page.getByRole('button',{name:'Save draft'}).click();
    await page.getByRole('status').filter({hasText:'Save not confirmed'}).waitFor();
    assert.equal(await page.locator('#id_photos').evaluate(input=>input.files.length),2);
    await context.setOffline(false);
    await page.getByRole('button',{name:'Save draft'}).click();
    await page.getByRole('status').filter({hasText:'Saved on the server'}).waitFor();
    assert.equal(await page.locator('#id_photos').evaluate(input=>input.files.length),0);
    assert.equal(await page.locator('[data-photo-controls] img').count(),2);
    await page.getByRole('button',{name:'Review audience'}).click();
    await page.getByRole('heading',{name:'Who can read this?'}).waitFor();
    assert.equal(await page.locator('.review img').count(),2);
    await page.getByRole('checkbox',{name:'I have reviewed'}).check();
    await page.getByRole('button',{name:'Confirm & submit'}).click();
    await page.getByRole('heading',{name:'Home moments'}).waitFor();
    assert.equal(await page.getByRole('img',{name:/Entry photo/}).count(),2);
    const response = await context.request.get(new URL(await page.getByRole('img',{name:'Entry photo 1',exact:true}).getAttribute('src'),process.env.JOURNAL_BROWSER_URL).href);
    assert.equal(response.status(),200);
    assert.ok(response.headers()['cache-control'].includes('no-store'));
    await page.evaluate(async () => { await navigator.serviceWorker.ready; });
    assert.equal(await page.evaluate(async () => {
      for (const name of await caches.keys()) {
        for (const request of await (await caches.open(name)).keys()) {
          if (new URL(request.url).pathname.startsWith('/entries/')) return false;
        }
      }
      return true;
    }), true);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    fs.mkdirSync('test-results',{recursive:true});
    await page.screenshot({path:'test-results/entry-with-photos.png',fullPage:true});
    await page.getByRole('link',{name:'Edit your entry'}).click();
    await page.getByRole('checkbox',{name:'Remove photo 1',exact:true}).check();
    await page.getByRole('button',{name:'Review audience'}).click();
    await page.getByRole('heading',{name:'Who can read this?'}).waitFor();
    assert.equal(await page.locator('.review img').count(),1);
    await page.getByRole('checkbox',{name:'I have reviewed'}).check();
    await page.getByRole('button',{name:'Confirm & submit'}).click();
    await page.getByRole('heading',{name:'Previous versions'}).waitFor();
    assert.equal(await page.getByRole('img',{name:/Entry photo/}).count(),1);
    await page.locator('details').first().locator('summary').click();
    assert.equal(await page.getByRole('img',{name:/Previous-version photo/}).count(),2);
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exit(1);});
