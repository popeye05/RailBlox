import {test,expect} from '@playwright/test';

test('evidence assessment, recommendation, officer decision, outcomes and report review',async({page})=>{
 await page.setViewportSize({width:1440,height:1000});
 await page.goto('/queue?corridor=presentation');
 await expect(page.getByRole('heading',{name:'Block queue',exact:true}).first()).toBeVisible();
 await page.getByRole('button',{name:'Review evidence',exact:true}).first().click();
 await expect(page.getByRole('heading',{name:/Evidence for/})).toBeVisible();
 await page.getByLabel('Security of the defect',{exact:true}).fill('2');
 await page.getByRole('button',{name:'Save priority assessment'}).click();
 await expect(page.getByRole('status').filter({hasText:'Assessment saved completed.'})).toBeVisible();
 await page.keyboard.press('Escape');
 await page.getByRole('button',{name:'Recommend block plan',exact:true}).click();
 await expect(page.getByRole('status').filter({hasText:'Recommendation completed.'})).toBeVisible({timeout:45000});
 await page.getByRole('link',{name:'Inspect saved schedule',exact:true}).click();
 await expect(page.getByText('EXISTING BLOCKS / PLANNING HOLDS',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Table alternative',exact:true}).click();
 await expect(page.getByRole('cell').filter({hasText:'WX-01'})).toBeVisible();
 await page.goBack();
 await expect(page.getByRole('button',{name:'Approve recommendation',exact:true})).toBeDisabled();
 await page.getByLabel('Officer review reason').fill('Reviewed source evidence, forecast allowance and work protection in the synthetic demo.');
 await page.getByRole('button',{name:'Approve recommendation',exact:true}).click();
 await expect(page.getByRole('status').filter({hasText:'Approval completed.'})).toBeVisible();
 await page.reload();await expect(page.getByRole('button',{name:'Approve recommendation',exact:true})).toBeDisabled();
 await page.screenshot({path:'qa-screenshots/queue-review-1440.png',fullPage:true});
 await page.getByRole('link',{name:'Reporting',exact:true}).click();
 await page.getByLabel('Execution narrative').fill('Equipment failure delayed completion by 15 minutes.');
 await page.getByRole('button',{name:'Save actual outcome'}).click();
 await expect(page.getByRole('status').filter({hasText:'Outcome recording completed.'})).toBeVisible();
 await page.getByRole('button',{name:'Prepare report draft'}).click();
 await expect(page.getByRole('heading',{name:'MIS report draft'})).toBeVisible();
 await page.getByLabel('Report review reason').fill('Checked saved evidence and remaining missing actuals.');
 await page.getByRole('button',{name:'Record draft review'}).click();
 await expect(page.getByText('reviewed draft',{exact:true})).toBeVisible();
 const downloaded=page.waitForEvent('download');await page.getByRole('link',{name:'Export draft JSON'}).click();expect((await downloaded).suggestedFilename()).toContain('railblox-draft');
 await page.screenshot({path:'qa-screenshots/report-reviewed-1440.png',fullPage:true});
 await page.getByRole('link',{name:'Insights',exact:true}).click();
 await page.getByLabel('Original incident narrative').fill('No signal failure at P1-UP; crew unavailable for 20 minutes.');
 await page.getByRole('button',{name:'Analyze narrative'}).click();
 await expect(page.getByRole('cell',{name:'Negated; do not count as a cause',exact:true})).toBeVisible();
 await expect(page.getByRole('cell',{name:'Resources',exact:true})).toBeVisible();
});

for(const width of [1440,390])test(`decision support routes at ${width}px`,async({page})=>{
 await page.setViewportSize({width,height:1000});
 for(const [route,title]of [['queue','Block queue'],['operations','Operations'],['insights','Insights'],['reports','Reporting']]){
  await page.goto('/'+route+'?corridor=presentation');
  await expect(page.getByRole('heading',{name:title,exact:true}).first()).toBeVisible();
  await expect(page.getByText('Synthetic advisory',{exact:true})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.screenshot({path:`qa-screenshots/${route}-${width}.png`,fullPage:true});
 }
 if(width===1440){await page.goto('/queue');await expect(page.getByText('Synthetic advisory',{exact:true})).toBeVisible();await page.evaluate(()=>document.documentElement.style.zoom='2');expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);}
});
