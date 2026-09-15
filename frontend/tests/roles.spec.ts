import {test,expect,type Page} from '@playwright/test';
type Role='viewer'|'planner'|'officer'|'admin';
const supabase='https://role-tests.supabase.co';
const id='00000000-0000-0000-0000-000000000001';

async function account(page:Page,role:Role|null,mfa=false){
 const user={id,email:'staff@example.test',aud:'authenticated',app_metadata:{railblox_role:role,railblox_division:'prototype'},user_metadata:{full_name:'Railway Colleague',designation:'',department:'',location:''},created_at:new Date().toISOString()};
 const token=[{alg:'HS256',typ:'JWT'},{sub:id,aud:'authenticated',exp:Math.floor(Date.now()/1000)+3600},'test'].map(v=>Buffer.from(typeof v==='string'?v:JSON.stringify(v)).toString('base64url')).join('.');
 let current=role;let verified=!mfa;
 await page.route('**/api/auth/config',route=>route.fulfill({json:{mode:'supabase',supabase_url:supabase,publishable_key:'sb_publishable_test',division:'prototype',public_signup_enabled:true,collect_date_of_birth:false}}));
 await page.route(supabase+'/auth/v1/**',route=>{
  const path=route.request().url();
  if(path.includes('/token'))return route.fulfill({json:{access_token:token,refresh_token:'test-refresh',token_type:'bearer',expires_in:3600,user}});
  if(path.includes('/logout'))return route.fulfill({status:204});
  if(route.request().method()==='PUT'&&path.endsWith('/user'))Object.assign(user.user_metadata,route.request().postDataJSON().data);
  return route.fulfill({json:user});
 });
 await page.route('**/api/auth/me',route=>route.fulfill({json:{id,email:user.email,name:user.user_metadata.full_name,designation:user.user_metadata.designation,department:user.user_metadata.department,location:user.user_metadata.location,role:current,division:'prototype',access_pending:!current,mfa_required:mfa,aal:verified?'aal2':'aal1'}}));
 await page.goto('/queue');
 await page.getByLabel('Work email').fill(user.email);
 await page.getByLabel('Password',{exact:true}).fill('not-a-real-password');
 await page.getByRole('button',{name:'Sign in to workspace'}).click();
 return {assign:(value:Role)=>{current=value},verify:()=>{verified=true}};
}

for(const role of ['viewer','planner','officer','admin'] as Role[])test(`${role} controls, read access, profile and administration`,async({page})=>{
 await account(page,role);
 const plan=role!=='viewer',officer=['officer','admin'].includes(role);
 await expect(page.getByRole('button',{name:'Recommend block plan',exact:true}))[plan?'toBeEnabled':'toBeDisabled']();
 await page.goto('/planner');
 await expect(page.getByRole('button',{name:'Validate',exact:true}))[officer?'toBeEnabled':'toBeDisabled']();
 await expect(page.getByRole('link',{name:'Export JSON',exact:true})).toBeVisible();
 await page.goto('/benchmarks');
 await expect(page.getByRole('button',{name:'Run four methods'}))[officer?'toBeEnabled':'toBeDisabled']();
 await page.goto('/tasks');
 await expect(page.getByRole('button',{name:'Add task',exact:true}))[plan?'toBeEnabled':'toBeDisabled']();
 await page.goto('/insights');
 await expect(page.getByRole('button',{name:'Analyze narrative'}))[plan?'toBeEnabled':'toBeDisabled']();
 if(role==='admin')await expect(page.getByRole('button',{name:'Save automation settings'})).toBeVisible();
 else await expect(page.getByRole('button',{name:'Save automation settings'})).toHaveCount(0);
 await page.getByRole('link',{name:/Profile & security/}).click();
 await expect(page.getByRole('heading',{name:'Your profile',exact:true})).toBeVisible();
 await expect(page.getByRole('link',{name:/Profile & security/})).toHaveAttribute('aria-current','page');
 await page.screenshot({path:`qa-screenshots/spec3-${role}-profile-desktop.png`,fullPage:true});
 await page.setViewportSize({width:390,height:844});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:`qa-screenshots/spec3-${role}-profile-mobile.png`,fullPage:true});
 await page.getByRole('button',{name:'Access permissions',exact:true}).click();await expect(page.getByRole('table')).toBeVisible();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.goto('/admin/users');
 if(role!=='admin')await expect(page.getByText('Administrator access is required to manage users.')).toBeVisible();
 else await expect(page.getByRole('heading',{name:'User access',exact:true})).toBeVisible();
});

test('pending account gains only the role assigned by administrator',async({page})=>{
 const control=await account(page,null);
 await expect(page.getByRole('heading',{name:'Awaiting access approval'})).toBeVisible();
 control.assign('viewer');
 await page.getByRole('button',{name:'Check access again'}).click();
 await expect(page.getByRole('button',{name:'Recommend block plan'})).toBeDisabled();
});

test('profile edits persist and role changes refresh on focus',async({page})=>{
 const control=await account(page,'planner');
 await page.getByRole('link',{name:/Profile & security/}).click();
 await page.getByLabel('Full name').fill('Updated Colleague');await page.getByLabel('Designation').fill('Section Engineer');await page.getByRole('combobox',{name:'Department',exact:true}).selectOption('Engineering');await page.getByLabel('Office / station').fill('Aravalli');await page.getByRole('button',{name:'Save profile'}).click();
 await expect(page.getByRole('status').filter({hasText:'Profile saved.'})).toBeVisible();
 await expect(page.getByRole('link',{name:/Updated Colleague Profile/})).toBeVisible();
 await page.reload();await expect(page.getByLabel('Designation')).toHaveValue('Section Engineer');await expect(page.getByLabel('Office / station')).toHaveValue('Aravalli');
 await page.goto('/planner');await expect(page.getByRole('button',{name:'Validate',exact:true})).toBeDisabled();
 control.assign('officer');await page.evaluate(()=>window.dispatchEvent(new Event('focus')));
 await expect(page.getByRole('button',{name:'Validate',exact:true})).toBeEnabled();
});

test('MFA gate challenges an enrolled authenticator before opening records',async({page})=>{
 const control=await account(page,'officer',true);
 await expect(page.getByRole('heading',{name:'Verify your authenticator'})).toBeVisible();
 await page.route(supabase+'/auth/v1/user',route=>route.fulfill({json:{id,aud:'authenticated',factors:[{id:'factor',factor_type:'totp',status:'verified',friendly_name:'Test factor'}]}}));
 await page.reload();
 await expect(page.getByLabel('Authentication code')).toBeVisible();
 await page.route(supabase+'/auth/v1/factors/factor/challenge',route=>route.fulfill({json:{id:'challenge',expires_at:Math.floor(Date.now()/1000)+60}}));
 await page.route(supabase+'/auth/v1/factors/factor/verify',async route=>{
  expect(route.request().postDataJSON().code).toBe('123456');control.verify();
  return route.fulfill({json:{access_token:'verified-test-session',refresh_token:'test-refresh',token_type:'bearer',expires_in:3600,user:{id,email:'staff@example.test',aud:'authenticated'}}});
 });
 await page.getByLabel('Authentication code').fill('123456');await page.getByRole('button',{name:'Verify and continue'}).click();
 await expect(page.getByRole('button',{name:'Recommend block plan'})).toBeVisible();
});

test('officer verifies and approves a recommendation with evidence',async({page})=>{
 await account(page,'officer');
 // The decision support flow may already have approved the presentation baseline;
 // review that same evidence so the solver can retain its committed assignments.
 await page.goto('/queue?corridor=presentation&day=0');
 await page.getByRole('button',{name:'Recommend block plan'}).click();
 await expect(page.getByRole('status').filter({hasText:'Recommendation completed.'})).toBeVisible();
 await page.getByLabel('Officer review reason').fill('Officer reviewed source evidence and constraints.');
 await page.getByRole('button',{name:'Approve recommendation',exact:true}).click();
 await expect(page.getByRole('status').filter({hasText:'Approval completed.'})).toBeVisible();
 await page.getByRole('link',{name:'Inspect saved schedule'}).click();
 await page.getByRole('button',{name:'Validate',exact:true}).click();
 await expect(page.getByRole('status').filter({hasText:'Validate plan completed.'})).toBeVisible();
});

test('admin invitation, reviewed grant and audit feedback',async({page})=>{
 const newcomer={id:'00000000-0000-0000-0000-000000000002',email:'new@example.test',name:'New Officer',role:null as string|null,division:null as string|null,requested_role:'officer',confirmed_at:'2026-09-11'};
 let invited=false,granted=false;
 await page.route('**/api/admin/users?*',route=>route.fulfill({json:{users:[newcomer],page:1,has_more:false}}));
 await page.route('**/api/status',route=>route.fulfill({json:{revision:'test',user_administration:true,updates:'Polling',realtime:'Unavailable',source_connections:'Not configured',external_ai:'Disabled',database:'SQLite'}}));
 await page.route('**/api/admin/audit?*',route=>route.fulfill({json:granted?[{id:'event',at:new Date().toISOString(),kind:'user-access-updated',record_id:newcomer.id,data:{actor:id,reason:'Appointment verified',assigned_role:'officer'}}]:[]}));
 await page.route('**/api/admin/invitations',route=>{invited=true;expect(route.request().postDataJSON().requested_role).toBe('officer');return route.fulfill({json:{message:'Sent'}})});
 await page.route('**/api/admin/users/'+newcomer.id,route=>{const body=route.request().postDataJSON();expect(body.expected_role).toBe(null);expect(body.reason).toBe('Appointment verified');newcomer.role=body.role;newcomer.division='prototype';granted=true;return route.fulfill({json:newcomer})});
 await account(page,'admin');await page.goto('/admin/users');
 await page.getByLabel('Colleague name').fill('New Officer');await page.getByLabel('Invitation email').fill(newcomer.email);await page.getByLabel('Proposed role').selectOption('officer');
 await page.getByRole('button',{name:'Send invitation email'}).click();
 await expect(page.getByRole('status').filter({hasText:'Invitation sent.'})).toBeVisible();expect(invited).toBe(true);
 await page.getByRole('button',{name:'Review access',exact:true}).click();await page.getByLabel('Assigned role',{exact:true}).selectOption('officer');await page.getByLabel('Access change reason').fill('Appointment verified');await page.getByRole('button',{name:'Confirm access assignment'}).click();
 await expect(page.getByRole('cell',{name:'user-access-updated',exact:true})).toBeVisible();expect(granted).toBe(true);
 await page.screenshot({path:'qa-screenshots/spec3-admin-review-desktop.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:'qa-screenshots/spec3-admin-review-mobile.png',fullPage:true});
});
