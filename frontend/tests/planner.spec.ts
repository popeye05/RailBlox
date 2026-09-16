import {test,expect} from '@playwright/test';

test('planner opportunity, disruption, repair, compare, approve and export',async({page,request})=>{
 const context=await (await request.get('http://127.0.0.1:8001/api/context')).json();const small=context.corridors.find((c:{id:string})=>c.id==='small');
 const run=await (await request.post('http://127.0.0.1:8001/api/plans/generate',{data:{snapshot_id:small.snapshot_id,core_only:true}})).json();
 let id='';for(let i=0;i<100;i++){const r=await (await request.get(`http://127.0.0.1:8001/api/runs/${run.id}`)).json();if(r.status==='succeeded'){id=r.result_id;break}await page.waitForTimeout(100)}
 expect(id).toBeTruthy();await page.goto('/planner?corridor=small&plan='+id);
 await expect(page.getByRole('heading',{name:'Maintenance planner',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'PK-W1',exact:true}).click();await expect(page.getByRole('heading',{name:'Executable work package'})).toBeVisible();await expect(page.getByText('60 min',{exact:true})).toBeVisible();await page.getByRole('button',{name:'Close details'}).click();
 await page.getByRole('link',{name:'Opportunities',exact:true}).click();await page.getByRole('button',{name:'Discover compatible work'}).click();
 const bundle=page.locator('article').filter({has:page.getByRole('heading',{name:'B + C',exact:true})});await expect(bundle.getByText('Compatible',{exact:true})).toBeVisible();await bundle.getByRole('button',{name:'Add to proposed plan'}).click();await expect(page.getByRole('status').filter({hasText:'Add opportunity completed.'})).toBeVisible();
 await page.getByRole('link',{name:'Planner',exact:true}).click();await page.getByRole('button',{name:'PK-W1',exact:true}).click();await expect(page.getByText('75 min',{exact:true})).toBeVisible();await page.keyboard.press('Escape');
 await page.getByRole('link',{name:'Disruption lab',exact:true}).click();await page.getByLabel('Minutes',{exact:true}).fill('20');await page.getByRole('button',{name:'Create scenario snapshot'}).click();await expect(page.getByRole('heading',{name:'Changed inputs'})).toBeVisible();await expect(page).toHaveURL(/[?&]scenario=[^&]+/);await page.reload();await expect(page.getByRole('heading',{name:'Changed inputs'})).toBeVisible();await page.getByRole('button',{name:'Repair plan',exact:true}).click();await expect(page.getByRole('status').filter({hasText:'Repair plan completed.'})).toBeVisible();
 await page.getByRole('button',{name:'Compare before / after'}).click();await expect(page.getByRole('heading',{name:'Assignment changes'})).toBeVisible();await expect(page.getByRole('cell',{name:'Deferred',exact:true})).toBeVisible();await page.keyboard.press('Escape');
 await page.getByRole('link',{name:'Planner',exact:true}).click();await page.getByRole('button',{name:'Validate',exact:true}).click();await expect(page.getByText('Passed modeled checks',{exact:true})).toBeVisible();await page.getByRole('button',{name:'Approve proposal'}).click();await page.getByRole('button',{name:'Record approval'}).click();await expect(page.getByText('approved',{exact:true})).toBeVisible();
 const downloadPromise=page.waitForEvent('download');await page.getByRole('link',{name:'Export JSON'}).click();const download=await downloadPromise;expect(download.suggestedFilename()).toMatch(/railblox.*json/);
});

for(const width of [1440,1024,390])test(`responsive planner ${width}px`,async({page})=>{
 await page.setViewportSize({width,height:1000});await page.goto('/planner');await expect(page.getByRole('heading',{name:'Maintenance planner',exact:true})).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
 const brand=page.getByRole('img',{name:'RailBLOX',exact:true});await expect(brand).toBeVisible();expect(await brand.evaluate((img:HTMLImageElement)=>img.complete&&img.naturalWidth>0)).toBe(true);
 await expect(page.getByRole('navigation',{name:'Operations navigation'}).getByRole('link')).toHaveCount(4);
 if(width===390){await page.getByRole('button',{name:'Menu',exact:true}).click();await expect(page.getByRole('navigation',{name:'Supporting navigation'})).toBeVisible();await page.getByRole('link',{name:'Maintenance',exact:true}).click();await expect(page.getByRole('heading',{name:'Maintenance',exact:true})).toBeVisible();await page.getByRole('link',{name:'Planner',exact:true}).click();await expect(page.getByRole('button',{name:'Menu',exact:true})).toHaveAttribute('aria-expanded','false');}
 else {await expect(page.getByRole('navigation',{name:'Supporting navigation'})).toBeVisible();await expect(page.getByRole('link',{name:'Planner',exact:true})).toHaveAttribute('aria-current','page');}
 await page.screenshot({path:`qa-screenshots/planner-${width}.png`,fullPage:true});await page.screenshot({path:`qa-screenshots/planner-viewport-${width}.png`,fullPage:false});
 await page.getByRole('button',{name:'Table alternative'}).click();await expect(page.getByRole('columnheader',{name:'Start IST'})).toBeVisible();
 await page.keyboard.press('Tab');expect(await page.evaluate(()=>document.activeElement?.tagName)).not.toBe('BODY');
});

test('200 percent zoom and all routes',async({page})=>{
 await page.setViewportSize({width:1440,height:1000});await page.goto('/planner');await expect(page.getByRole('heading',{name:'Maintenance planner',exact:true})).toBeVisible();await page.evaluate(()=>{document.documentElement.style.zoom='2'});await page.screenshot({path:'qa-screenshots/planner-zoom-200.png',fullPage:true});const overflow=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,nodes:[...document.querySelectorAll('*')].filter(e=>e.getBoundingClientRect().right>innerWidth+1&&!e.closest('.timeline-scroll,.diagram-scroll,.table-scroll')).slice(0,8).map(e=>({tag:e.tagName,class:e.className,right:e.getBoundingClientRect().right}))}));expect(overflow.scroll,JSON.stringify(overflow)).toBeLessThanOrEqual(overflow.width);
 await page.evaluate(()=>{document.documentElement.style.zoom='1'});
 for(const [route,title] of [['/tasks','Maintenance'],['/data','Data review'],['/opportunities','Opportunities'],['/disruptions','Disruption lab'],['/benchmarks','Results']]){await page.goto(route);await expect(page.getByRole('heading',{name:title,exact:true})).toBeVisible();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);await page.screenshot({path:`qa-screenshots/${route.slice(1)}-1440.png`,fullPage:true})}
});

test('benchmark results persist on refresh and task history opens',async({page})=>{
 await page.goto('/planner');await expect(page.getByRole('heading',{name:'Maintenance planner',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'A Track geometry correction on timeline',exact:true}).focus();await page.keyboard.press('Enter');await expect(page.getByRole('heading',{name:'Saved assignment history'})).toBeVisible();await expect(page.getByRole('cell').filter({hasText:'W1 ·'}).first()).toBeVisible();await page.keyboard.press('Escape');
 await page.getByRole('link',{name:'Results',exact:true}).click();await page.getByRole('button',{name:'Run four methods'}).click();await expect(page.getByRole('cell',{name:'Adaptive repair planner',exact:true})).toBeVisible();await page.reload();await expect(page.getByRole('cell',{name:'Adaptive repair planner',exact:true})).toBeVisible();await expect(page.getByLabel('Saved benchmark')).toBeVisible();
});
