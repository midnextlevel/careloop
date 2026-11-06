const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  const context=await browser.newContext({serviceWorkers:'block',viewport:{width:390,height:844}});
  await context.addCookies([{name:'sessionid',value:process.env.JOURNAL_BROWSER_SESSION,url:process.env.JOURNAL_BROWSER_URL}]);
  const page=await context.newPage();
  await page.goto(process.env.JOURNAL_BROWSER_URL);
  await page.getByRole('button',{name:'Write an entry'}).click();
  await page.getByLabel('Daily summary').fill('Snapshot sent before the latest edits');
  let release,seen;
  const gate=new Promise(r=>release=r),received=new Promise(r=>seen=r);
  await page.route('**/edit/',async route=>{
   if(route.request().method()!=='POST')return route.continue();
   const response=await route.fetch();seen();await gate;await route.fulfill({response});
  },{times:1});
  await page.getByRole('button',{name:'Review audience'}).click();
  await received;
  await page.getByLabel('Daily summary').fill('Latest typed text that should be preserved');
  release();
  await page.getByRole('status').filter({hasText:'Review again to include your latest changes'}).waitFor();
  assert.equal(await page.getByLabel('Daily summary').inputValue(),'Latest typed text that should be preserved');
  assert.equal(await page.locator('.review').count(),0);
  await page.getByRole('button',{name:'Review audience'}).click();
  await page.getByRole('heading',{name:'Who can read this?'}).waitFor();
  assert.ok((await page.locator('.review').innerText()).includes('Latest typed text that should be preserved'));
  await page.getByRole('checkbox').check();
  await page.getByRole('button',{name:'Confirm & submit'}).click();
  await page.getByRole('heading',{name:'School moments'}).waitFor();
  assert.equal(await page.getByText('Latest typed text that should be preserved',{exact:true}).count(),1);
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
