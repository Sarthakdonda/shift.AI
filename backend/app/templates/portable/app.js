'use strict';
(() => {
  const spec=window.APP_SPEC, store=window.shiftStorage;
  const main=document.querySelector('main'), nav=document.querySelector('nav'), status=document.querySelector('#status');
  let selected=spec.entities[0]?.name, search='', sort='', filter='';
  const el=(tag,text,attrs={})=>{
    const node=document.createElement(tag);
    if(text!==null) node.textContent=text;
    Object.entries(attrs).forEach(([k,v])=>node.setAttribute(k,v));
    return node;
  };
  const button=(text,fn)=>{const b=el('button',text,{type:'button'});b.onclick=()=>run(fn);return b;};
  const field=(name,input)=>{const label=el('label',null);label.append(el('span',name),input);return label;};
  async function run(fn) {
    status.textContent='';
    try {await fn();} catch(error) {status.textContent=error.message||'The operation failed. Please retry.';status.focus();}
  }
  document.querySelector('#brand').textContent=spec.name;
  document.title=spec.name;
  document.documentElement.style.setProperty('--accent',spec.accent);
  document.querySelector('#menu').onclick=()=>{const open=nav.classList.toggle('open');document.querySelector('#menu').setAttribute('aria-expanded',String(open));};
  function navigate() {
    nav.replaceChildren();
    for(const page of spec.public_pages) nav.append(el('a',page.title,{href:'#page/'+page.slug}));
    for(const entity of spec.entities) nav.append(el('a',entity.label,{href:'#module/'+entity.name}));
    if(spec.entities.length) nav.append(el('a','Backup & storage',{href:'#storage'}));
  }
  function website(slug) {
    const page=spec.public_pages.find(p=>p.slug===slug);
    if(!page){main.replaceChildren(el('h1','Page not found'),el('a','Return home',{href:'#'}));return;}
    document.title=page.title+' · '+spec.name;
    document.querySelector('meta[name=description]').content=page.description;
    main.replaceChildren(el('h1',page.title),el('p',page.description,{class:'intro'}));
    for(const section of page.sections) {
      const block=el('section',null,{class:'content '+section.layout});
      block.append(el('h2',section.heading));
      if(section.image_url) block.append(el('img',null,{src:section.image_url,alt:section.image_alt||section.heading,loading:'lazy',referrerpolicy:'no-referrer'}));
      else if(section.layout==='gallery') block.append(el('div','Add your approved photography here.',{class:'image-placeholder'}));
      if(section.layout==='cards') {
        const cards=el('div',null,{class:'cards'});
        section.text.split('\n').filter(Boolean).forEach(text=>cards.append(el('article',text)));
        block.append(cards);
      } else block.append(el('p',section.text));
      main.append(block);
    }
    if(page.contact_email) main.append(el('a','Email '+page.contact_email,{href:'mailto:'+page.contact_email,class:'contact-action'}));
    document.querySelector('footer').textContent=spec.name+' · '+new Date().getFullYear();
  }
  async function moduleView() {
    const entity=spec.entities.find(e=>e.name===selected);
    if(!entity){main.replaceChildren(el('h1','Module not found'));return;}
    const records=await store.list(entity.name);
    main.replaceChildren();
    const header=el('div',null,{class:'section-heading'});
    header.append(el('div',null),button('Add '+entity.label,()=>editor(entity)));
    header.firstChild.append(el('h1',entity.label),el('p',records.length+' records stored on this device.'));
    main.append(header);
    const tools=el('div',null,{class:'toolbar'});
    const searchInput=el('input',null,{type:'search',placeholder:'Search records','aria-label':'Search records'});
    searchInput.value=search;
    const sortInput=el('select',null,{'aria-label':'Sort records'});
    sortInput.append(el('option','Newest first',{value:''}));
    entity.fields.forEach(f=>sortInput.append(el('option',f.label,{value:f.name})));
    sortInput.value=sort;
    const filterField=entity.fields.find(f=>f.kind==='select');
    const filterInput=el('select',null,{'aria-label':'Filter records'});
    filterInput.append(el('option','All records',{value:''}));
    filterField?.options.forEach(o=>filterInput.append(el('option',o,{value:o})));
    filterInput.value=filter;
    tools.append(searchInput,sortInput);
    if(filterField)tools.append(filterInput);
    main.append(tools);
    const wrap=el('div',null,{class:'table-wrap'});
    const table=el('table',null),thead=el('thead',null),tr=el('tr',null),tbody=el('tbody',null);
    entity.fields.forEach(f=>tr.append(el('th',f.label,{scope:'col'})));tr.append(el('th','Actions',{scope:'col'}));
    thead.append(tr);table.append(thead,tbody);wrap.append(table);main.append(wrap);
    const references={};
    for(const f of entity.fields.filter(f=>f.kind==='reference')) {
      const target=spec.entities.find(e=>e.name===f.reference);
      references[f.name]=Object.fromEntries((await store.list(f.reference)).map(r=>[r.id,String(r.payload[target.fields[0].name]||r.id)]));
    }
    function render() {
      tbody.replaceChildren();
      const visible=records.filter(r=>Object.values(r.payload).join(' ').toLowerCase().includes(search.toLowerCase())&&(!filter||r.payload[filterField.name]===filter));
      visible.sort((a,b)=>sort?String(a.payload[sort]??'').localeCompare(String(b.payload[sort]??''),undefined,{numeric:true}):b.created_at.localeCompare(a.created_at));
      for(const record of visible) {
        const row=el('tr',null);
        entity.fields.forEach(f=>row.append(el('td',String(references[f.name]?.[record.payload[f.name]]??record.payload[f.name]??'—'))));
        const actions=el('td',null,{class:'record-actions'});
        actions.append(button('Edit',()=>editor(entity,record)),button('Delete',async()=>{if(confirm('Delete this record? This cannot be undone without a backup.')){await store.remove(entity.name,record.id);await moduleView();}}));
        entity.transitions.forEach((t,i)=>{if(record.payload[t.field]===t.from_value)actions.append(button(t.label,async()=>{await store.transition(entity.name,record.id,i);await moduleView();}));});
        row.append(actions);tbody.append(row);
      }
      if(!visible.length){const row=el('tr',null);row.append(el('td',search||filter?'No matching records.':'No records yet. Add the first record to get started.',{colspan:String(entity.fields.length+1)}));tbody.append(row);}
    }
    searchInput.oninput=()=>{search=searchInput.value;render();};
    sortInput.onchange=()=>{sort=sortInput.value;render();};
    filterInput.onchange=()=>{filter=filterInput.value;render();};
    render();
  }
  async function editor(entity,record=null) {
    const dialog=el('dialog',null),form=el('form',null),inputs={};
    form.append(el('h2',(record?'Edit ':'Add ')+entity.label));
    for(const f of entity.fields) {
      let input;
      if(f.calculation?.length || entity.transitions.some(t=>t.field===f.name)) {
        input=el('input',null,{readonly:'',value:String(record?.payload[f.name]??(f.calculation?.length?'Calculated on save':entity.transitions.find(t=>t.field===f.name).from_value))});
      } else if(f.kind==='select'||f.kind==='reference') {
        input=el('select',null);input.append(el('option','Choose '+f.label,{value:''}));
        if(f.kind==='select') f.options.forEach(o=>input.append(el('option',o,{value:o})));
        else {
          const target=spec.entities.find(e=>e.name===f.reference);
          (await store.list(f.reference)).forEach(r=>input.append(el('option',String(r.payload[target.fields[0].name]||r.id),{value:r.id})));
        }
        input.value=record?.payload[f.name]??'';
      } else {
        input=el('input',null,{type:f.kind==='boolean'?'checkbox':['number','date','email'].includes(f.kind)?f.kind:'text'});
        if(f.kind==='number')input.step='any';
        if(f.kind==='boolean')input.checked=!!record?.payload[f.name];else input.value=record?.payload[f.name]??'';
      }
      input.name=f.name;
      input.setAttribute('aria-label',f.label);
      if(f.required&&!f.calculation?.length&&f.kind!=='boolean')input.required=true;
      inputs[f.name]=input;form.append(field(f.label,input));
    }
    const message=el('p','',{role:'alert'});
    const submit=el('button','Save record',{type:'submit'});
    form.append(message,submit,button('Cancel',()=>dialog.close()));
    form.onsubmit=async event=>{
      event.preventDefault();submit.disabled=true;message.textContent='';
      try {
        const data=Object.fromEntries(entity.fields.filter(f=>!f.calculation?.length).map(f=>[f.name,f.kind==='boolean'?inputs[f.name].checked:inputs[f.name].value]));
        await store.save(entity.name,data,record?.id);dialog.close();await moduleView();
      } catch(error){message.textContent=error.message;} finally{submit.disabled=false;}
    };
    dialog.append(form);document.body.append(dialog);dialog.onclose=()=>dialog.remove();dialog.showModal();
  }
  function storageView() {
    main.replaceChildren(el('h1','Backup & storage'),el('p','Records stay on this device in '+store.adapter+'. Other browsers and downloaded apps have separate databases. Transfer records with a backup.'));
    main.append(el('p','Clearing browser storage or changing the application origin can remove access to browser records. Keep independent backups. A forgotten encryption passphrase cannot be recovered.'));
    const pass=el('input',null,{type:'password',minlength:'12',autocomplete:'new-password','aria-label':'Backup passphrase'});
    main.append(field('Backup passphrase (required for sensitive data)',pass));
    main.append(button('Export backup',async()=>{await store.download(await store.backup(pass.value));status.textContent='Backup created. Store it separately from this device.';}));
    const file=el('input',null,{type:'file',accept:'.json,application/json','aria-label':'Choose backup'});
    main.append(field('Choose a backup to restore',file),button('Restore backup',async()=>{
      if(!file.files[0])throw Error('Choose a backup file.');
      if(file.files[0].size>10*1024*1024)throw Error('Choose a backup under 10 MB.');
      if(confirm('Merge this backup into the current application? Records with matching IDs will be replaced.')){await store.restore(await file.files[0].text(),pass.value);status.textContent='Backup restored. Existing unrelated records were preserved.';}
    }),button('Request persistent browser storage',async()=>{status.textContent=await store.persist()?'Persistent storage granted. Continue keeping backups.':'Persistence was not granted or is unavailable; continue keeping backups.';}));
    if(spec.sensitive_data)main.append(button('Lock application',()=>location.reload()));
  }
  async function route() {
    nav.classList.remove('open');
    const path=location.hash.slice(1);
    if(path==='storage')return storageView();
    if(path.startsWith('module/')){const next=path.slice(7);if(next!==selected){search='';sort='';filter='';}selected=next;return moduleView();}
    if(path.startsWith('page/'))return website(path.slice(5));
    if(path){main.replaceChildren(el('h1','Page not found'),el('a','Return home',{href:'#'}));return;}
    if(spec.public_pages.length)return website(spec.public_pages[0].slug);
    return moduleView();
  }
  async function start(password='') {
    if(spec.entities.length) {
      const state=await store.init(password);
      if(state.locked) {
        main.replaceChildren(el('h1',state.initial?'Protect your local records':'Unlock your application'),el('p','Use a passphrase of at least 12 characters. It encrypts your local records and is never sent to shift.AI.'));
        const form=el('form',null),input=el('input',null,{type:'password',minlength:'12',required:'',autocomplete:state.initial?'new-password':'current-password','aria-label':'Application passphrase'});
        form.append(field('Application passphrase',input),el('button',state.initial?'Create encrypted database':'Unlock',{type:'submit'}));
        form.onsubmit=event=>{event.preventDefault();run(()=>start(input.value));};main.append(form);return;
      }
    }
    navigate();await route();window.onhashchange=()=>run(route);
    if('serviceWorker' in navigator && !location.pathname.startsWith('/_portable/') && !window.__TAURI_INTERNALS__) navigator.serviceWorker.register('./sw.js').catch(()=>{});
    window.shiftApp={ready:true,spec,storage:store};
  }
  run(()=>start());
})();
