import {test,expect,type Page} from '@playwright/test';

async function mockAccount(page:Page,options:{enrolled?:boolean;role?:string;policy?:boolean;extraFactor?:boolean}={}){
  const host='https://mfa-account.supabase.co';
  let enrolled=!!options.enrolled,assured=false,pending=false,cancelled=false,extraFactor=!!options.extraFactor;
  const removed:string[]=[];
  const user={id:'00000000-0000-0000-0000-000000000082',email:'viewer@example.test',aud:'authenticated',user_metadata:{full_name:'Test Colleague'}};
  const token=()=>[{alg:'HS256',typ:'JWT'},{sub:user.id,aal:assured?'aal2':'aal1',aud:'authenticated',exp:Math.floor(Date.now()/1000)+3600},'test'].map(v=>Buffer.from(typeof v==='string'?v:JSON.stringify(v)).toString('base64url')).join('.');
  const providerUser=()=>({...user,factors:[...(enrolled||pending?[{id:'totp-test',friendly_name:'Primary',factor_type:'totp',status:enrolled?'verified':'unverified'}]:[]),...(extraFactor?[{id:'totp-backup',friendly_name:'Backup',factor_type:'totp',status:'verified'}]:[])]});
  const session=()=>({access_token:token(),refresh_token:'test-refresh',token_type:'bearer',expires_in:3600,user:providerUser()});
  await page.route('**/api/auth/config',r=>r.fulfill({json:{mode:'supabase',supabase_url:host,publishable_key:'sb_publishable_test',division:'prototype',public_signup_enabled:true}}));
  await page.route('**/api/auth/me',r=>r.fulfill({json:{...user,name:'Test Colleague',role:options.role||'viewer',division:'prototype',aal:assured?'aal2':'aal1',mfa_enrolled:enrolled||extraFactor,mfa_required:enrolled||extraFactor||(options.policy&&options.role!=='viewer'),mfa_policy_enabled:!!options.policy}}));
  await page.route(host+'/auth/v1/**',r=>{
    const url=r.request().url(),method=r.request().method();
    if(url.includes('/token')){assured=false;return r.fulfill({json:session()})}
    if(url.includes('/logout')){assured=false;return r.fulfill({status:204})}
    if(url.endsWith('/factors')&&method==='POST'){pending=true;return r.fulfill({json:{id:'totp-test',type:'totp',totp:{qr_code:'<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200"><rect width="200" height="200" fill="white"/></svg>',secret:'TEST-SETUP-KEY',uri:'otpauth://totp/test'}}})}
    if(url.endsWith('/factors/totp-test')&&method==='DELETE'){if(enrolled){expect(assured).toBe(true);removed.push('totp-test')}else cancelled=true;pending=false;enrolled=false;return r.fulfill({json:{id:'totp-test'}})}
    if(url.endsWith('/factors/totp-backup')&&method==='DELETE'){expect(assured).toBe(true);extraFactor=false;removed.push('totp-backup');return r.fulfill({json:{id:'totp-backup'}})}
    if(url.endsWith('/challenge'))return r.fulfill({json:{id:'challenge',expires_at:Math.floor(Date.now()/1000)+60}});
    if(url.endsWith('/verify')){
      if(r.request().postDataJSON().code!=='123456')return r.fulfill({status:422,json:{msg:'Invalid authenticator code',code:'mfa_verification_failed'}});
      enrolled=true;pending=false;assured=true;return r.fulfill({json:session()});
    }
    return r.fulfill({json:providerUser()});
  });
  return {cancelled:()=>cancelled,enrolled:()=>enrolled||extraFactor,removed,addFactor:()=>{extraFactor=true}};
}
async function login(page:Page){
  await page.getByLabel('Username or work email').fill('viewer@example.test');
  await page.getByLabel('Password',{exact:true}).fill('test-password');
  await page.getByRole('button',{name:'Sign in to workspace'}).click();
}

async function openEnrolledSecurity(page:Page){
  await page.goto('/profile');await login(page);
  await page.getByLabel('Authentication code').fill('123456');
  await page.getByRole('button',{name:'Verify and continue'}).click();
  await page.getByRole('button',{name:'Security',exact:true}).click();
}

test('disable MFA can be cancelled, rejects bad codes, and removes the next login challenge',async({page})=>{
  const state=await mockAccount(page,{enrolled:true});await openEnrolledSecurity(page);
  await page.getByRole('button',{name:'Disable MFA',exact:true}).click();
  const confirmation=page.getByRole('form',{name:'Disable MFA confirmation'});
  await confirmation.getByRole('button',{name:'Cancel',exact:true}).click();
  expect(state.removed).toEqual([]);expect(state.enrolled()).toBe(true);
  await page.getByRole('button',{name:'Disable MFA',exact:true}).click();
  await confirmation.getByLabel('Authentication code').fill('000000');
  await confirmation.getByRole('button',{name:'Confirm disable MFA'}).click();
  await expect(page.getByRole('alert')).toContainText('Invalid authenticator code');
  expect(state.removed).toEqual([]);
  await page.screenshot({path:'qa-screenshots/mfa-disable-confirmation.png',fullPage:true});
  await confirmation.getByLabel('Authentication code').fill('123456');
  await confirmation.getByRole('button',{name:'Confirm disable MFA'}).click();
  await expect(page.getByRole('button',{name:'Enable MFA',exact:true})).toBeVisible();
  expect(state.removed).toEqual(['totp-test']);expect(state.enrolled()).toBe(false);
  await page.getByRole('button',{name:'Log out',exact:true}).click();await login(page);
  await expect(page.getByRole('heading',{name:'Your profile',exact:true})).toBeVisible();
  await expect(page.getByRole('heading',{name:'Verify your authenticator'})).toHaveCount(0);
});

test('disable MFA preserves protection on provider failure and can be retried',async({page})=>{
  const state=await mockAccount(page,{enrolled:true});await openEnrolledSecurity(page);
  const endpoint='https://mfa-account.supabase.co/auth/v1/factors/totp-test';
  await page.route(endpoint,r=>r.request().method()==='DELETE'?r.fulfill({status:422,json:{msg:'Unable to remove authenticator'}}):r.fallback());
  await page.getByRole('button',{name:'Disable MFA',exact:true}).click();
  await page.getByLabel('Authentication code').fill('123456');await page.getByRole('button',{name:'Confirm disable MFA'}).click();
  await expect(page.getByRole('alert')).toContainText('Unable to remove authenticator');
  expect(state.enrolled()).toBe(true);expect(state.removed).toEqual([]);
  await expect(page.getByText('MFA is enabled for your account.',{exact:true})).toBeVisible();
  await page.unroute(endpoint);
  await page.getByLabel('Authentication code').fill('123456');await page.getByRole('button',{name:'Confirm disable MFA'}).click();
  await expect(page.getByRole('button',{name:'Enable MFA',exact:true})).toBeVisible();
});

test('multiple authenticators require explicit confirmation and the verified factor is removed last',async({page})=>{
  const state=await mockAccount(page,{enrolled:true,extraFactor:true});await openEnrolledSecurity(page);
  await page.getByRole('button',{name:'Disable MFA',exact:true}).click();
  await expect(page.getByRole('form',{name:'Disable MFA confirmation'})).toContainText('all 2 authenticators');
  await page.getByLabel('Authenticator to verify').selectOption('totp-backup');
  await page.getByLabel('Authentication code').fill('123456');await page.getByRole('button',{name:'Confirm disable MFA'}).click();
  await expect(page.getByRole('button',{name:'Enable MFA',exact:true})).toBeVisible();
  expect(state.removed).toEqual(['totp-test','totp-backup']);
});

test('factor changes during confirmation abort removal',async({page})=>{
  const state=await mockAccount(page,{enrolled:true});await openEnrolledSecurity(page);
  await page.getByRole('button',{name:'Disable MFA',exact:true}).click();
  await expect(page.getByRole('form',{name:'Disable MFA confirmation'})).toBeVisible();state.addFactor();
  await page.getByLabel('Authentication code').fill('123456');await page.getByRole('button',{name:'Confirm disable MFA'}).click();
  await expect(page.getByRole('alert')).toContainText('Your authenticators changed');expect(state.removed).toEqual([]);
});

test('partial removal is reported and remaining MFA stays enabled',async({page})=>{
  const state=await mockAccount(page,{enrolled:true,extraFactor:true});await openEnrolledSecurity(page);
  await page.route('https://mfa-account.supabase.co/auth/v1/factors/totp-test',r=>r.request().method()==='DELETE'?r.fulfill({status:422,json:{msg:'Removal failed'}}):r.fallback());
  await page.getByRole('button',{name:'Disable MFA',exact:true}).click();
  await page.getByLabel('Authentication code').fill('123456');await page.getByRole('button',{name:'Confirm disable MFA'}).click();
  await expect(page.getByRole('alert')).toContainText('Some authenticators were removed');
  await expect(page.getByText('MFA is enabled for your account.',{exact:true})).toBeVisible();
  expect(state.removed).toEqual(['totp-backup']);expect(state.enrolled()).toBe(true);
});

for(const role of ['officer','viewer'])test(`division MFA policy is respected for ${role}`,async({page})=>{
  const state=await mockAccount(page,{enrolled:true,policy:true,role});await openEnrolledSecurity(page);
  const disable=page.getByRole('button',{name:'Disable MFA',exact:true});
  if(role==='officer'){
    await expect(disable).toBeDisabled();await expect(page.getByText('MFA is required by your division policy.')).toBeVisible();
  }else{
    await disable.click();await page.getByLabel('Authentication code').fill('123456');await page.getByRole('button',{name:'Confirm disable MFA'}).click();
    await expect(page.getByRole('button',{name:'Enable MFA',exact:true})).toBeVisible();expect(state.enrolled()).toBe(false);
  }
});

test('voluntary MFA activates only after verification and challenges the next password sign-in',async({page})=>{
  const state=await mockAccount(page);
  await page.goto('/profile');await login(page);
  await page.getByRole('button',{name:'Security',exact:true}).click();
  await page.getByRole('button',{name:'Enable MFA',exact:true}).click();
  await expect(page.getByRole('img',{name:'Authenticator enrollment QR code'})).toBeVisible();
  await page.getByLabel('Authentication code').fill('000000');
  await page.getByRole('button',{name:'Verify and enable MFA'}).click();
  await expect(page.getByRole('alert')).toContainText('Invalid authenticator code');
  expect(state.enrolled()).toBe(false);
  await page.getByLabel('Authentication code').fill('123456');
  await page.getByRole('button',{name:'Verify and enable MFA'}).click();
  await expect(page.getByText('MFA is enabled for your account.',{exact:true})).toBeVisible();
  await expect(page.getByRole('img',{name:'Authenticator enrollment QR code'})).toHaveCount(0);
  await expect(page.getByText('TEST-SETUP-KEY',{exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'Log out',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Sign in',exact:true})).toBeVisible();
  await page.reload();await expect(page.getByRole('heading',{name:'Sign in',exact:true})).toBeVisible();
  await login(page);
  await expect(page.getByRole('heading',{name:'Verify your authenticator'})).toBeVisible();
  await expect(page.getByRole('heading',{name:'Your profile',exact:true})).toHaveCount(0);
  await page.getByLabel('Authentication code').fill('000000');await page.getByRole('button',{name:'Verify and continue'}).click();
  await expect(page.getByRole('alert')).toContainText('Invalid authenticator code');
  await page.getByLabel('Authentication code').fill('123456');await page.getByRole('button',{name:'Verify and continue'}).click();
  await expect(page.getByRole('heading',{name:'Your profile',exact:true})).toBeVisible();
});

test('cancelling unfinished enrollment does not enable MFA',async({page})=>{
  const state=await mockAccount(page);await page.goto('/profile');await login(page);
  await page.getByRole('button',{name:'Security',exact:true}).click();
  await page.getByRole('button',{name:'Enable MFA',exact:true}).click();
  await page.getByRole('button',{name:'Cancel setup'}).click();
  await expect(page.getByRole('button',{name:'Enable MFA',exact:true})).toBeVisible();
  expect(state.cancelled()).toBe(true);expect(state.enrolled()).toBe(false);
  await page.getByRole('button',{name:'Log out',exact:true}).click();await login(page);
  await expect(page.getByRole('heading',{name:'Your profile',exact:true})).toBeVisible();
});

test('local logout reports remote revocation failure without restoring workspace access',async({page})=>{
  await mockAccount(page);await page.goto('/profile');await login(page);
  await page.route('https://mfa-account.supabase.co/auth/v1/logout*',r=>r.fulfill({status:400,json:{msg:'Remote sign-out unavailable'}}));
  await page.getByRole('button',{name:'Log out',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Sign in',exact:true})).toBeVisible();
  await expect(page.getByRole('status')).toContainText('Remote sign-out could not be confirmed');
  await page.reload();await expect(page.getByRole('heading',{name:'Sign in',exact:true})).toBeVisible();
});

for(const width of [1440,390,320])test(`black and white login, Figtree and visible logout at ${width}px`,async({page})=>{
  await mockAccount(page);await page.setViewportSize({width,height:1000});await page.goto('/queue');
  await expect(page.getByRole('heading',{name:'Sign in',exact:true})).toBeVisible();
  await expect(page.locator('.auth-intro')).toHaveCSS('background-color','rgb(255, 255, 255)');
  await expect(page.locator('.auth-signin')).toHaveCSS('background-color','rgb(17, 17, 17)');
  expect(await page.locator('body').evaluate(e=>getComputedStyle(e).fontFamily)).toContain('Figtree');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
  await page.screenshot({path:`qa-screenshots/brand-login-${width}.png`,fullPage:true});
  await login(page);await expect(page.getByRole('button',{name:'Log out',exact:true})).toBeVisible();
  await expect(page.locator('.operations-navigation a.active')).toHaveCSS('background-color','rgb(230, 184, 63)');
  await expect(page.locator('.workspace-sync,.role-notice')).toHaveCount(0);
  await expect(page.getByRole('button',{name:'Recommend block plan',exact:true})).toBeVisible();
  await expect(page.locator('.environment-label')).not.toContainText('prototype');
  await expect(page.locator('.workspace-bottom')).not.toContainText('prototype');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
  await page.screenshot({path:`qa-screenshots/brand-workspace-${width}.png`,fullPage:true});
});
