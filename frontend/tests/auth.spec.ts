import {test,expect} from '@playwright/test';

test('Supabase sign-in gate, authenticated download and sign-out',async({page})=>{
 const supabase='https://testproject.supabase.co';
 await page.route('**/api/auth/config',route=>route.fulfill({json:{mode:'supabase',supabase_url:supabase,publishable_key:'sb_publishable_browser_test',division:'prototype',public_signup_enabled:true,collect_date_of_birth:true}}));
 const user={id:'00000000-0000-0000-0000-000000000001',email:'officer@example.test',aud:'authenticated',app_metadata:{railblox_role:'officer',railblox_division:'prototype'},user_metadata:{},created_at:new Date().toISOString()};
 const token=[{alg:'HS256',typ:'JWT'},{sub:user.id,aud:'authenticated',exp:Math.floor(Date.now()/1000)+3600},'test'].map(v=>Buffer.from(typeof v==='string'?v:JSON.stringify(v)).toString('base64url')).join('.');
 await page.route(supabase+'/auth/v1/**',async route=>{
  if(route.request().url().includes('/token'))return route.fulfill({json:{access_token:token,refresh_token:'test-refresh',token_type:'bearer',expires_in:3600,expires_at:Math.floor(Date.now()/1000)+3600,user}});
  if(route.request().url().includes('/logout'))return route.fulfill({status:204});
  return route.fulfill({json:user});
 });
 await page.route('**/api/auth/me',route=>{
  expect(route.request().headers().authorization).toBe('Bearer '+token);
  return route.fulfill({json:{id:user.id,role:'officer',division:'prototype'}});
 });
 await page.setViewportSize({width:1440,height:1000});
 await page.goto('/queue?corridor=presentation');
 await expect(page.getByRole('heading',{name:'Sign in',exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'New user? Create an account'})).toBeVisible();
 await page.getByRole('button',{name:'New user? Create an account'}).click();
 await expect(page.getByRole('heading',{name:'Create an account',exact:true})).toBeVisible();
 await expect(page.getByText(/administrator must approve/)).toBeVisible();
 await page.getByRole('button',{name:'Back to sign in',exact:true}).click();
 await page.screenshot({path:'qa-screenshots/login-1440.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:'qa-screenshots/login-390.png',fullPage:true});
 await page.getByLabel('Username or work email').fill(user.email);
 await page.getByLabel('Password',{exact:true}).fill('test-password-not-real');
 await page.getByRole('button',{name:'Sign in to workspace'}).click();
 await expect(page.getByRole('heading',{name:'Block queue',exact:true,level:1})).toBeVisible();
 await page.goto('/operations?corridor=presentation');
 const request=page.waitForRequest(r=>r.url().includes('/evidence/')&&r.url().endsWith('/sample'));
 const download=page.waitForEvent('download');
 await page.getByRole('link',{name:'Download evidence JSON'}).click();
 expect((await request).headers().authorization).toBe('Bearer '+token);
 expect((await download).suggestedFilename()).toBe('railblox-evidence.json');
 await page.getByRole('link',{name:/Profile & security/}).click();
 await page.getByRole('button',{name:'Security',exact:true}).click();
 await page.getByRole('button',{name:'Sign out',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Sign in',exact:true})).toBeVisible();
});

test('local learning and persisted automation controls',async({page})=>{
 await page.goto('/insights?corridor=presentation');
 await page.getByRole('button',{name:'Train and evaluate duration model'}).click();
 await expect(page.getByText(/Model MAE:/)).toBeVisible();
 await page.getByLabel('Prepare report drafts',{exact:true}).check();
 await page.getByLabel('Interval (minutes)',{exact:true}).fill('15');
 await page.getByRole('button',{name:'Save automation settings'}).click();
 await page.reload();
 await expect(page.getByLabel('Prepare report drafts',{exact:true})).toBeChecked();
 await expect(page.getByLabel('Interval (minutes)',{exact:true})).toHaveValue('15');
 await page.getByRole('button',{name:'Run monitoring now'}).click();
 await expect(page.getByRole('cell',{name:'succeeded',exact:true}).first()).toBeVisible();
 await expect(page.getByRole('button',{name:'Send text for AI extraction'})).toBeDisabled();
});
