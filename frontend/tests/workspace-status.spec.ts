import {test,expect} from '@playwright/test';

test('background updates stay quiet; failures offer retry and recovery clears the notice',async({page})=>{
  let unavailable=false,statusRequests=0;
  await page.route('**/api/status',r=>{statusRequests++;return unavailable?r.fulfill({status:503,json:{detail:'Temporarily unavailable'}}):r.fulfill({json:{revision:'quiet-test'}})});
  await page.goto('/queue');
  await expect(page.getByRole('heading',{name:'Block queue',exact:true,level:1})).toBeVisible();
  await expect.poll(()=>statusRequests).toBeGreaterThan(0);
  await expect(page.locator('.workspace-sync,.role-notice')).toHaveCount(0);
  await expect(page.getByText(/Workspace checks every|Last checked/)).toHaveCount(0);
  unavailable=true;await page.reload();
  await expect(page.getByRole('status').filter({hasText:'Workspace updates unavailable.'})).toBeVisible();
  unavailable=false;await page.getByRole('button',{name:'Retry refresh'}).click();
  await expect(page.locator('.workspace-sync')).toHaveCount(0);
});

test('revision polling still refreshes workspace data without status chatter',async({page})=>{
  let revision='first',statusRequests=0,contextRequests=0;
  await page.route('**/api/status',r=>{statusRequests++;return r.fulfill({json:{revision}})});
  await page.route('**/api/context*',r=>{contextRequests++;return r.continue()});
  await page.clock.install();await page.goto('/queue');
  await expect(page.getByRole('heading',{name:'Block queue',exact:true,level:1})).toBeVisible();
  await expect.poll(()=>statusRequests).toBeGreaterThan(0);
  const previous=contextRequests,requests=statusRequests;revision='second';
  await page.clock.fastForward(31000);
  await expect.poll(()=>statusRequests).toBeGreaterThan(requests);
  await expect.poll(()=>contextRequests).toBeGreaterThan(previous);
  await expect(page.locator('.workspace-sync')).toHaveCount(0);
});
