/* Product build validator: only compiler-owned pages in a fresh, network-blocked browser. */
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const root=path.resolve(process.argv[2]);
const allowed=new Set(['index.html','style.css','app.js','storage.js','spec.js','spec.json','release.json','icon.svg','manifest.webmanifest','sw.js']);
const mime={'.html':'text/html','.css':'text/css','.js':'text/javascript','.json':'application/json','.webmanifest':'application/manifest+json','.svg':'image/svg+xml'};
const server=http.createServer((req,res)=>{
  const name=new URL(req.url,'http://localhost').pathname.slice(1)||'index.html';
  if(!allowed.has(name)){res.writeHead(404).end();return;}
  res.setHeader('Content-Type',mime[path.extname(name)]||'text/plain');res.end(fs.readFileSync(path.join(root,name)));
});
(async()=>{
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const base='http://127.0.0.1:'+server.address().port;
  const browser=await chromium.launch({headless:true,chromiumSandbox:true});
  const checks=[];
  try {
    const context=await browser.newContext({serviceWorkers:'block'});
    await context.route('**/*',route=>new URL(route.request().url()).origin===base?route.continue():route.abort());
    const page=await context.newPage(),errors=[];
    page.on('pageerror',error=>errors.push(error.message));
    await page.goto(base);
    const spec=JSON.parse(fs.readFileSync(path.join(root,'spec.json'),'utf8'));
    if(spec.sensitive_data){
      await page.getByLabel('Application passphrase',{exact:true}).fill('isolated-validation-passphrase');
      await page.getByRole('button',{name:'Create encrypted database',exact:true}).click();
    }
    await page.waitForFunction(()=>window.shiftApp?.ready);
    checks.push('browser_startup');
    for(const p of spec.public_pages){
      await page.evaluate(slug=>{location.hash='page/'+slug},p.slug);
      await page.getByRole('heading',{level:1,name:p.title,exact:true}).waitFor();
    }
    if(spec.public_pages.length)checks.push('website_navigation');
    if(spec.entities.length){
      const result=await page.evaluate(async()=>{
        const s=window.shiftStorage,spec=window.APP_SPEC,created={},pending=[...spec.entities];
        function sample(field){
          if(field.kind==='reference')return created[field.reference]?.id||null;
          if(field.kind==='number')return 10;
          if(field.kind==='boolean')return true;
          if(field.kind==='date')return '2026-01-15';
          if(field.kind==='email')return 'sample@example.invalid';
          if(field.kind==='select')return field.options[0];
          return 'Validation '+field.label;
        }
        while(pending.length){
          const i=pending.findIndex(e=>e.fields.every(f=>f.kind!=='reference'||!f.required||created[f.reference]));
          if(i<0)throw Error('Unresolvable required references');
          const entity=pending.splice(i,1)[0];
          const data=Object.fromEntries(entity.fields.filter(f=>!f.calculation?.length).map(f=>[f.name,sample(f)]));
          created[entity.name]=await s.save(entity.name,data);
          const editable=entity.fields.find(f=>f.kind==='text'&&!entity.transitions.some(t=>t.field===f.name));
          if(editable){data[editable.name]='Updated validation record';created[entity.name]=await s.save(entity.name,data,created[entity.name].id);}
          const transitions=entity.transitions;
          if(transitions.length){
            const index=transitions.findIndex(t=>created[entity.name].payload[t.field]===t.from_value);
            if(index>=0)await s.transition(entity.name,created[entity.name].id,index);
          }
        }
        const backup=await s.backup('isolated-backup-passphrase');
        await s.restore(backup,'isolated-backup-passphrase');
        let corruptRejected=false;
        try{await s.restore(backup,'wrong-passphrase');}catch{corruptRejected=true;}
        if(!corruptRejected)throw Error('Invalid backup password accepted');
        return {names:Object.keys(created),first:created[spec.entities[0].name]};
      });
      checks.push('crud','relationships','workflow','encrypted_backup_restore');
      await page.reload();
      if(spec.sensitive_data){
        await page.getByLabel('Application passphrase',{exact:true}).fill('isolated-validation-passphrase');
        await page.getByRole('button',{name:'Unlock',exact:true}).click();
      }
      await page.waitForFunction(()=>window.shiftApp?.ready);
      assert.equal(await page.evaluate(async name=>(await shiftStorage.list(name)).length,spec.entities[0].name),1);
      checks.push('refresh_persistence');
      await page.evaluate(name=>{location.hash='module/'+name},spec.entities[0].name);
      await page.getByRole('button',{name:'Edit',exact:true}).first().waitFor();
      await page.getByRole('button',{name:'Edit',exact:true}).first().click();
      await page.getByRole('button',{name:'Save record',exact:true}).click();
      await page.waitForFunction(()=>!document.querySelector('dialog'));
      await page.getByLabel('Search records',{exact:true}).fill('no-matching-verification-record');
      await page.getByText('No matching records.',{exact:true}).waitFor();
      checks.push('interactive_forms_search');
      await page.evaluate(async()=>{
        const s=window.shiftStorage;
        const rows=(await Promise.all(APP_SPEC.entities.map(e=>s.list(e.name)))).flat();
        let progress=true;
        while(rows.length&&progress){progress=false;for(const r of [...rows]){try{await s.remove(r.entity,r.id);rows.splice(rows.indexOf(r),1);progress=true;}catch{}}}
        if(rows.length) {
          // Optional cycles are allowed: clear their references before deleting.
          for(const row of rows){const entity=APP_SPEC.entities.find(e=>e.name===row.entity);for(const f of entity.fields)if(f.kind==='reference'&&!f.required)row.payload[f.name]=null;await s.save(row.entity,row.payload,row.id);}
          for(const row of rows)await s.remove(row.entity,row.id);
        }
      });
      checks.push('delete');
    }
    await page.setViewportSize({width:390,height:844});
    await page.evaluate(()=>{location.hash=''});
    await page.waitForTimeout(100);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
    assert.deepEqual(errors,[]);
    checks.push('mobile_layout','no_runtime_errors');
    console.log(JSON.stringify({status:'passed',checks,logs:['Executed Chromium acceptance checks against compiled files. No customer records or external services used.'],limitations:['Synthetic representative inputs; external providers, native installation and arbitrary business scenarios require separate acceptance.']}));
  } finally {await browser.close();await new Promise(resolve=>server.close(resolve));}
})().catch(error=>{console.error(error.stack);server.close();process.exitCode=1;});
