import {test,expect} from '@playwright/test';

test('a provisioned corridor without a plan offers a first-plan action',async({page})=>{
  await page.route('**/api/context',async route=>{const response=await route.fetch();const data=await response.json();await route.fulfill({json:{...data,plans:[]}})});
  await page.goto('/planner?corridor=small');
  await expect(page.getByRole('heading',{name:'No saved plan',exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'Generate first plan'})).toBeEnabled();
});

test('direct availability route waits for data and recovers from a source failure',async({page})=>{
  let unavailable=true;
  await page.route('**/api/availability/summary?*',route=>unavailable?route.fulfill({status:503,json:{message:'Evidence service interrupted'}}):route.continue());
  await page.goto('/availability?corridor=small');
  await expect(page.getByRole('heading',{name:'Availability',exact:true})).toBeVisible();
  await expect(page.getByText('Availability evidence unavailable',{exact:true})).toBeVisible();
  unavailable=false;await page.getByRole('button',{name:'Retry availability'}).click();
  await expect(page.getByRole('heading',{name:'Know what the plan protects'})).toBeVisible();
  await expect(page.getByRole('heading',{name:'This page could not be displayed'})).toHaveCount(0);
});

test('train enquiry filters, station order, detail inspection and matching CSV export',async({page})=>{
  await page.goto('/traffic?corridor=small');
  await expect(page.getByRole('heading',{name:'Section occupancy chart'})).toBeVisible();
  await page.getByLabel('Train ID',{exact:true}).fill('FRT');
  await expect(page.getByRole('button',{name:'Inspect train FRT-01',exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'Inspect train PAX-01',exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'Inspect train FRT-01',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Train FRT-01',exact:true})).toBeVisible();
  await expect(page.getByRole('dialog').getByRole('cell',{name:'S1-UP',exact:true})).toBeVisible();
  await page.keyboard.press('Escape');
  const downloadPromise=page.waitForEvent('download');await page.getByRole('link',{name:'Export CSV',exact:true}).click();
  const download=await downloadPromise;expect(download.suggestedFilename()).toBe('railblox-train-enquiry.csv');
  await page.getByRole('button',{name:'Reset enquiry'}).click();
  await page.getByRole('combobox',{name:'Direction',exact:true}).selectOption('DN');
  await expect(page.getByRole('button',{name:'Inspect train PAX-01'})).toBeVisible();
  await page.reload();await expect(page.getByRole('combobox',{name:'Direction',exact:true})).toHaveValue('DN');
  await page.getByRole('combobox',{name:'From station',exact:true}).selectOption('DVR');
  await page.getByRole('combobox',{name:'To station',exact:true}).selectOption('ARV');
  await expect(page.getByRole('button',{name:'Inspect train PAX-01'})).toBeVisible();
  await page.getByRole('button',{name:'Inspect train PAX-01'}).click();
  await expect(page.getByRole('dialog').getByRole('cell',{name:'DVR → CHN',exact:true})).toBeVisible();
  await page.keyboard.press('Escape');
  await page.getByLabel('Train ID',{exact:true}).fill('NO-SUCH-TRAIN');
  await expect(page.getByRole('heading',{name:'No trains match this enquiry'})).toBeVisible();
});

test('operational registers filter real evidence and export matching rows',async({page})=>{
  await page.goto('/operations?corridor=small');
  await expect(page.getByRole('heading',{name:'Operational registers'})).toBeVisible();
  await page.getByLabel('Register range').selectOption('all');
  await page.getByRole('button',{name:'Incident evidence',exact:true}).click();
  await expect(page.getByRole('columnheader',{name:'Recorded delay minutes'})).toBeVisible();
  const download=page.waitForEvent('download');await page.getByRole('button',{name:'Export register CSV'}).click();
  expect((await download).suggestedFilename()).toBe('railblox-operational-register.csv');
  await page.getByLabel('Search register').fill('NO-SUCH-RECORD');
  await expect(page.getByText('No matching incident evidence in this range.',{exact:false})).toBeVisible();
  await expect(page.getByRole('button',{name:'Export register CSV'})).toBeDisabled();
});

for(const width of [1440,1024,390])test(`polished pages fit ${width}px without console failures`,async({page})=>{
  const errors:string[]=[];page.on('pageerror',error=>errors.push(error.message));
  await page.setViewportSize({width,height:1000});
  for(const [path,heading] of [['profile','Your profile'],['traffic','Train movements'],['availability','Availability'],['help','Workspace guide']]){
    await page.goto(`/${path}?corridor=small`);await expect(page.getByRole('heading',{name:heading,exact:true})).toBeVisible();
    if(path==='traffic')await expect(page.getByRole('heading',{name:'Section occupancy chart'})).toBeVisible();
    if(path==='availability')await expect(page.getByRole('heading',{name:'Know what the plan protects'})).toBeVisible();
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),path).toBe(true);
    await page.screenshot({path:`qa-screenshots/polish-${path}-${width}.png`,fullPage:true});
    if(path==='profile')for(const tab of ['Security','Access permissions','Activity']){
      await page.getByRole('button',{name:tab,exact:true}).click();
      if(tab==='Access permissions')await expect(page.getByRole('table')).toBeVisible();
      const layout=await page.evaluate(()=>({viewport:innerWidth,width:document.documentElement.scrollWidth,nodes:[...document.querySelectorAll('main,.profile-page,.panel,.table-scroll,.permissions-table')].map(element=>({name:element.className||element.tagName,width:element.getBoundingClientRect().width,right:element.getBoundingClientRect().right,overflow:getComputedStyle(element).overflowX}))}));
      expect(layout.width,tab+': '+JSON.stringify(layout)).toBeLessThanOrEqual(layout.viewport);
      await page.screenshot({path:`qa-screenshots/polish-profile-${tab.toLowerCase().replaceAll(' ','-')}-${width}.png`,fullPage:true});
    }
  }
  expect(errors).toEqual([]);
});
