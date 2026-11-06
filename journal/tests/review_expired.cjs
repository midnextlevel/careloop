const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  const context=await browser.newContext({serviceWorkers:'block'});
  await context.addCookies([{name:'sessionid',value:process.env.JOURNAL_BROWSER_SESSION,url:process.env.JOURNAL_BROWSER_URL}]);
  const page=await context.newPage();
  await page.goto(process.env.JOURNAL_BROWSER_URL);
  await page.getByRole('button',{name:'Write an entry'}).click();
  await page.getByLabel('Daily summary').fill('Successfully saved but UI reports failure');
  await page.getByRole('button',{name:'Review audience'}).click();
  await page.getByRole('heading',{name:'Who can read this?'}).waitFor();
  await page.getByRole('checkbox').check();
  await page.getByRole('button',{name:'Confirm & submit'}).click();
  await page.getByRole('heading',{name:'Day by day'}).waitFor();
  await page.getByText('Entry submitted.',{exact:true}).waitFor();
  assert.equal(await page.locator('.review').count(),0);
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
