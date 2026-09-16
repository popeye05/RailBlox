import {test,expect} from '@playwright/test';

for(const width of [1440,1024,768,390,320])test(`masthead and split navigation at ${width}px`,async({page})=>{
  await page.setViewportSize({width,height:1000});
  await page.goto('/planner?corridor=small&day=2');
  await expect(page.getByRole('heading',{name:'Maintenance planner',exact:true})).toBeVisible();
  const header=page.getByRole('banner');
  await expect(header.getByRole('link',{name:'RailBLOX home'})).toBeVisible();
  const operations=page.getByRole('navigation',{name:'Operations navigation'});
  await expect(operations.getByRole('link')).toHaveText(['Block queue','Planner','Train movements','Operations']);
  const logo=await header.getByRole('link',{name:'RailBLOX home'}).boundingBox();
  const tabs=await operations.boundingBox();
  expect(logo!.y+logo!.height).toBeLessThan(tabs!.y);
  const support=page.getByRole('navigation',{name:'Supporting navigation'});
  if(width<=800){
    await expect(support).toBeHidden();
    await page.getByRole('button',{name:'Menu',exact:true}).click();
    await expect(support.getByRole('link',{name:'Maintenance',exact:true})).toBeFocused();
    await page.keyboard.press('Escape');
    await expect(support).toBeHidden();
    await expect(page.getByRole('button',{name:'Menu',exact:true})).toBeFocused();
    await page.getByRole('button',{name:'Menu',exact:true}).click();
  }
  await expect(support.getByRole('link',{name:'Planner',exact:true})).toHaveCount(0);
  await support.getByRole('link',{name:'Maintenance',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Maintenance',exact:true})).toBeVisible();
  expect(new URL(page.url()).searchParams.get('corridor')).toBe('small');
  expect(new URL(page.url()).searchParams.get('day')).toBe('2');
  if(width<=800)await expect(support).toBeHidden();
  await operations.getByRole('link',{name:'Planner',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Maintenance planner',exact:true})).toBeVisible();
  await expect(operations.getByRole('link',{name:'Planner',exact:true})).toHaveAttribute('aria-current','page');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
  await page.screenshot({path:`qa-screenshots/navigation-${width}.png`,fullPage:false});
  await header.getByRole('link',{name:/Profile & security/}).click();
  await expect(page.getByRole('heading',{name:'Your profile',exact:true})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
  await page.screenshot({path:`qa-screenshots/navigation-profile-${width}.png`,fullPage:false});
});

test('print view excludes both navigation surfaces',async({page})=>{
  await page.goto('/profile');
  await expect(page.getByRole('heading',{name:'Your profile',exact:true})).toBeVisible();
  await page.emulateMedia({media:'print'});
  await expect(page.getByRole('banner')).toBeHidden();
  await expect(page.getByRole('navigation',{name:'Supporting navigation'})).toBeHidden();
  await expect(page.getByRole('heading',{name:'Your profile',exact:true})).toBeVisible();
});
