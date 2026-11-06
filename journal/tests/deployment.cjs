const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:process.env.BROWSER_CHANNEL||'chrome'});
 try{
  const page=await browser.newPage({viewport:{width:390,height:844}});
  const base=process.env.JOURNAL_BROWSER_URL;
  fs.mkdirSync('test-results',{recursive:true});
  if(process.env.DENIAL_SESSION){
   await page.context().addCookies([{name:'sessionid',value:process.env.DENIAL_SESSION,url:base}]);
   const response=await page.goto(base);
   assert.equal(response.status(),403);
   await page.getByRole('heading',{name:'This account can’t access Careloop'}).waitFor();
   await page.getByRole('button',{name:'Try another Google account'}).waitFor();
   assert.ok(response.headers()['cache-control'].includes('no-store'));
   await page.screenshot({path:'test-results/careloop-access-denied.png',fullPage:true});
  }else{
   await page.goto(base+'/login/');
   await page.getByRole('heading',{name:'Welcome to your new Careloop'}).waitFor();
   await page.getByLabel('Private setup code').fill(process.env.SETUP_TEST_CODE);
   await page.getByRole('button',{name:'Unlock setup'}).click();
   await page.getByRole('heading',{name:'Connect your Careloop'}).waitFor();
   await page.getByLabel('Owner’s exact Google email').fill('first-owner@example.invalid');
   await page.getByLabel('Child’s display name').fill('Fictional Child');
   await page.getByLabel('Google OAuth client ID').fill('fictional.apps.googleusercontent.com');
   await page.getByLabel('Google OAuth client secret').fill('fictional-private-secret');
   await page.getByRole('checkbox').check();
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
   await page.screenshot({path:'test-results/careloop-first-deployment.png',fullPage:true});
   await page.getByRole('button',{name:'Finish deployment'}).click();
   await page.getByRole('heading',{name:'Your Careloop is ready to connect'}).waitFor();
   await page.getByRole('link',{name:'Continue to Careloop sign-in'}).click();
   await page.getByRole('button',{name:'Continue with Google'}).waitFor();
   assert.equal((await page.context().request.get(base+'/deployment/')).status(),404);
  }
  assert.equal(await page.locator('.brand-logo').evaluate(el=>el.complete&&el.naturalWidth>0),true);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
