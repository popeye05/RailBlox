import {test,expect} from '@playwright/test';

test('email-only signup, username session, uniqueness feedback, recovery and MFA-off notice',async({page})=>{
  const provider='https://username-test.supabase.co';
  const user={id:'00000000-0000-0000-0000-000000000071',email:'staff@example.test',aud:'authenticated',user_metadata:{full_name:'Test Colleague'},app_metadata:{railblox_role:'planner',railblox_division:'prototype'}};
  const token=[{alg:'HS256',typ:'JWT'},{sub:user.id,aud:'authenticated',exp:Math.floor(Date.now()/1000)+3600},'test'].map(v=>Buffer.from(typeof v==='string'?v:JSON.stringify(v)).toString('base64url')).join('.');
  let username:string|null=null;
  let passwordGrantCalls=0;
  await page.route('**/api/auth/config',route=>route.fulfill({json:{mode:'supabase',supabase_url:provider,publishable_key:'sb_publishable_test',division:'prototype',public_signup_enabled:true}}));
  await page.route(provider+'/auth/v1/**',route=>{
    const path=route.request().url();
    if(path.includes('/token')){passwordGrantCalls++;return route.fulfill({json:{access_token:token,refresh_token:'refresh-test',token_type:'bearer',expires_in:3600,user}})}
    if(path.includes('/logout'))return route.fulfill({status:204});
    return route.fulfill({json:user});
  });
  await page.route('**/api/auth/me',route=>route.fulfill({json:{id:user.id,email:user.email,name:'Test Colleague',role:'planner',division:'prototype',email_confirmed:true,aal:'aal1',mfa_required:false,mfa_policy_enabled:false}}));
  await page.route('**/api/auth/username',async route=>{
    if(route.request().method()==='PATCH'){
      const data=route.request().postDataJSON();
      if(data.username==='taken.name')return route.fulfill({status:409,json:{message:'That username is unavailable. Choose another name or reload your profile.'}});
      expect(data.expected_username).toBe(username);username=data.username.toLowerCase();
    }
    return route.fulfill({json:{username,enabled:true}});
  });
  await page.route('**/api/auth/username-login',route=>{
    const data=route.request().postDataJSON();
    expect(data).toEqual({username:'Rail.Operator',password:'test-password-only'});
    return route.fulfill({json:{access_token:token,refresh_token:'refresh-test'}});
  });
  await page.goto('/planner');
  await page.getByRole('button',{name:'New user? Create an account'}).click();
  await expect(page.getByLabel('Work email',{exact:false})).toHaveAttribute('type','email');
  await expect(page.getByLabel('Username',{exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'Back to sign in'}).click();
  await page.getByLabel('Username or work email').fill(user.email);
  await page.getByLabel('Password',{exact:true}).fill('test-password-only');
  await page.getByRole('button',{name:'Sign in to workspace'}).click();
  await expect(page.getByRole('heading',{name:'Maintenance planner',exact:true})).toBeVisible();
  expect(passwordGrantCalls).toBe(1);
  await page.goto('/profile');
  await page.getByLabel('Username',{exact:true}).fill('taken.name');
  await page.getByRole('button',{name:'Save username',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('That username is unavailable');
  await page.getByLabel('Username',{exact:true}).fill('Rail.Operator');
  await page.getByRole('button',{name:'Save username',exact:true}).click();
  await expect(page.getByRole('status')).toContainText('Username saved.');
  await page.reload();await expect(page.getByLabel('Username',{exact:true})).toHaveValue('rail.operator');
  await page.getByRole('button',{name:'Security',exact:true}).click();
  await expect(page.getByRole('button',{name:'Enable MFA',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Sign out',exact:true}).click();
  await page.getByLabel('Username or work email').fill('Rail.Operator');
  await page.getByRole('button',{name:'Forgot password?'}).click();
  await expect(page.getByRole('alert')).toContainText('Enter your work email, not your username');
  await page.getByLabel('Password',{exact:true}).fill('test-password-only');
  await page.getByRole('button',{name:'Sign in to workspace'}).click();
  await expect(page.getByRole('heading',{name:'Your profile',exact:true})).toBeVisible();
  expect(passwordGrantCalls).toBe(1); // username flow installs the returned Supabase session
  await expect(page.getByRole('heading',{name:'Verify your authenticator'})).toHaveCount(0);
  await page.screenshot({path:'qa-screenshots/next-phase-username.png',fullPage:true});
});

for(const width of [1440,390])test(`planning and decision support are distinct at ${width}px`,async({page})=>{
  const errors:string[]=[];page.on('pageerror',error=>errors.push(error.message));
  await page.setViewportSize({width,height:1000});
  await page.goto('/planner?corridor=small');
  await expect(page.getByRole('region',{name:'Workflow purpose'})).toContainText('Maintenance block planning');
  await page.goto('/availability?corridor=small');
  await expect(page.getByRole('region',{name:'Workflow purpose'})).toContainText('Predictive decision support');
  await page.getByRole('link',{name:'How the models work'}).click();
  await expect(page.getByRole('heading',{name:'Model & planning basis',exact:true})).toBeVisible();
  await expect(page.getByText('RailBLOX does',{exact:false})).toContainText('not implement');
  expect(new URL(page.url()).searchParams.get('corridor')).toBe('small');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
  await page.screenshot({path:`qa-screenshots/next-phase-methods-${width}.png`,fullPage:true});
  await page.getByRole('link',{name:'Open maintenance planner',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Maintenance planner',exact:true})).toBeVisible();
  expect(errors).toEqual([]);
});
