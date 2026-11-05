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
    await page.getByRole('link',{name:'Care team', exact:true}).waitFor();
    await page.getByRole('button',{name:'Write an entry'}).click();
    await page.getByLabel('Entry type').selectOption('home');
    await page.getByLabel('Daily summary').fill('Fictional test: Alex enjoyed reading at home.');
    await page.getByLabel('What helped').fill('A quiet room and a favourite picture book.');
    await page.getByRole('button',{name:'Save draft'}).click();
    await page.getByRole('status').filter({hasText:'Saved on the server'}).waitFor();
    await page.getByRole('button',{name:'Review audience'}).click();
    await page.getByRole('checkbox').check();
    await page.getByRole('button',{name:'Confirm & submit'}).click();
    await page.getByRole('heading',{name:'Home moments'}).waitFor();
    await page.getByText('Test Parent',{exact:true}).waitFor();
    const entryUrl = page.url();
    await page.getByRole('link',{name:'Back to journal'}).click();
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    fs.mkdirSync('test-results',{recursive:true});
    await page.screenshot({path:'test-results/named-account-timeline.png',fullPage:true});
    await page.getByRole('button',{name:'Sign out'}).click();
    await page.getByRole('heading',{name:'Welcome to the journal'}).waitFor();
    await page.goto(entryUrl);
    await page.getByRole('heading',{name:'Welcome to the journal'}).waitFor();
    console.log('PASS: named development login, owner controls, draft save, review, submit, named authorship, mobile layout, logout, anonymous denial.');
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exit(1);});
