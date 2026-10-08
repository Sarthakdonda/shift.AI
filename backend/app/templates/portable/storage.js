'use strict';
(() => {
  const spec = window.APP_SPEC, appId = window.APP_RELEASE.application_id;
  const dbName = 'shift-app-' + appId;
  const native = window.__TAURI_INTERNALS__;
  const request = r => new Promise((resolve, reject) => { r.onsuccess = () => resolve(r.result); r.onerror = () => reject(r.error); });
  let db, key;
  const b64 = bytes => btoa(Array.from(bytes, n => String.fromCharCode(n)).join(''));
  const bytes = value => Uint8Array.from(atob(value), c => c.charCodeAt(0));
  async function derive(password, salt) {
    if (password.length < 12) throw Error('Use a passphrase of at least 12 characters.');
    const material = await crypto.subtle.importKey('raw', new TextEncoder().encode(password), 'PBKDF2', false, ['deriveKey']);
    return crypto.subtle.deriveKey({name:'PBKDF2',salt:bytes(salt),iterations:210000,hash:'SHA-256'}, material, {name:'AES-GCM',length:256}, false, ['encrypt','decrypt']);
  }
  async function seal(value, encryptionKey, context) {
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const data = await crypto.subtle.encrypt({name:'AES-GCM',iv,additionalData:new TextEncoder().encode(context)}, encryptionKey, new TextEncoder().encode(JSON.stringify(value)));
    return {iv:b64(iv), data:b64(new Uint8Array(data))};
  }
  async function unseal(value, encryptionKey, context) {
    try {
      return JSON.parse(new TextDecoder().decode(await crypto.subtle.decrypt({name:'AES-GCM',iv:bytes(value.iv),additionalData:new TextEncoder().encode(context)}, encryptionKey, bytes(value.data))));
    } catch { throw Error('Unable to unlock data. Check the passphrase and backup integrity.'); }
  }
  const adapter = {
    async open() {
      if (native) return;
      if (!window.indexedDB) throw Error('Local database is unavailable. Open this application on a secure origin.');
      const opening = indexedDB.open(dbName, 1);
      opening.onupgradeneeded = () => {
        const database = opening.result;
        database.createObjectStore('meta', {keyPath:'id'});
        const records = database.createObjectStore('records', {keyPath:'id'});
        records.createIndex('entity', 'entity');
      };
      db = await request(opening);
      db.onversionchange = () => db.close();
    },
    async read() {
      if (native) return native.invoke('read_state');
      const tx = db.transaction(['meta','records'], 'readonly');
      const [meta, records] = await Promise.all([request(tx.objectStore('meta').get('state')),request(tx.objectStore('records').getAll())]);
      return {meta:meta?.value || {revision:0},records};
    },
    async list(entity) {
      if (native) return native.invoke('list_records', {entity});
      return request(db.transaction('records').objectStore('records').index('entity').getAll(entity));
    },
    async write(state, expected) {
      if (native) return native.invoke('write_state', {state,expected});
      return new Promise((resolve,reject) => {
        const tx = db.transaction(['meta','records'], 'readwrite');
        let conflict = false;
        tx.oncomplete = () => resolve();
        tx.onerror = () => reject(tx.error || Error('Database write failed.'));
        tx.onabort = () => reject(Error(conflict ? 'Another window changed these records. Reload and retry.' : 'Database write failed; existing records were preserved.'));
        const meta = tx.objectStore('meta'), records = tx.objectStore('records');
        const current = meta.get('state');
        current.onsuccess = () => {
          if ((current.result?.value?.revision || 0) !== expected) { conflict = true; tx.abort(); return; }
          meta.put({id:'state',value:state.meta});
          records.clear();
          state.records.forEach(row => records.put(row));
        };
      });
    }
  };
  const entityFor = name => {
    const entity = spec.entities.find(e => e.name === name);
    if (!entity) throw Error('Unknown record module.');
    return entity;
  };
  function compatible(previous) {
    for (const old of previous?.entities || []) {
      const next = spec.entities.find(e => e.name === old.name);
      if (!next) throw Error('This version removes a module. Open the previous version and back up before upgrading.');
      for (const field of old.fields) {
        const current = next.fields.find(f => f.name === field.name);
        if (!current || current.kind !== field.kind || current.reference !== field.reference ||
            (!field.required && current.required) || (field.options || []).some(o => !current.options.includes(o))) {
          throw Error('An incompatible schema change was blocked. Your existing data is preserved.');
        }
      }
      if (next.fields.some(f => f.required && !old.fields.some(p => p.name === f.name))) throw Error('New required fields need a reviewed migration.');
    }
  }
  async function decode(row) {
    if (row.encrypted && !key) throw Error('Unlock this application first.');
    return {...row, payload:row.encrypted ? await unseal(row.payload,key,appId+'/'+row.entity+'/'+row.id) : row.payload};
  }
  function calculate(tokens, record) {
    const stack = [];
    for (const token of tokens) {
      if (token === 'round') stack.push(Math.round(stack.pop()*100)/100);
      else if (['+','-','*','/','min','max'].includes(token)) {
        const b=stack.pop(),a=stack.pop();
        stack.push(token==='+'?a+b:token==='-'?a-b:token==='*'?a*b:token==='/'?a/b:token==='min'?Math.min(a,b):Math.max(a,b));
      } else stack.push(Number(Object.hasOwn(record,token)?record[token]:token));
    }
    if (stack.length !== 1 || !Number.isFinite(stack[0])) throw Error('Calculation failed. Check numeric inputs and division by zero.');
    return stack[0];
  }
  function validate(entity, data, all, old, transition=false) {
    const clean = {};
    if (!data || typeof data !== 'object' || Array.isArray(data)) throw Error('Invalid record.');
    for (const field of entity.fields) {
      let value = data[field.name];
      if (field.calculation?.length) continue;
      const workflow = entity.transitions.find(t => t.field === field.name);
      if (workflow && !transition) value = old ? old.payload[field.name] : workflow.from_value;
      if (value === undefined || value === null || value === '') {
        if (field.required) throw Error(field.label + ' is required.');
        clean[field.name] = field.kind === 'boolean' ? false : null; continue;
      }
      if (field.kind === 'number') { value = Number(value); if (!Number.isFinite(value)) throw Error(field.label+' must be a valid number.'); }
      else if (field.kind === 'boolean') { if (typeof value !== 'boolean') throw Error(field.label+' must be true or false.'); }
      else {
        if (typeof value !== 'string' || value.length > 10000) throw Error(field.label+' must contain valid text.');
        value=value.trim();
        if (field.required && !value) throw Error(field.label+' is required.');
        if (field.kind === 'email' && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) throw Error('Enter a valid '+field.label+'.');
        if (field.kind === 'date' && (!/^\d{4}-\d{2}-\d{2}$/.test(value) || new Date(value).toISOString().slice(0,10)!==value)) throw Error('Enter a valid '+field.label+'.');
        if (field.kind === 'select' && !field.options.includes(value)) throw Error('Choose a valid '+field.label+'.');
        if (field.kind === 'reference' && !all.some(r => r.entity === field.reference && r.id === value)) throw Error(field.label+' references a missing record.');
      }
      clean[field.name]=value;
    }
    for (const field of entity.fields.filter(f=>f.calculation?.length)) clean[field.name]=calculate(field.calculation,clean);
    return clean;
  }
  async function change(fn) {
    const state = await adapter.read();
    // An older open tab must not overwrite fields added by a newer release.
    compatible(state.meta.schema);
    if (state.meta.salt && !key) throw Error('Unlock this application first.');
    const all = await Promise.all(state.records.map(decode));
    const result = await fn(all, state.meta);
    if (all.length > 10000) throw Error('This local application supports up to 10,000 records. Export data before expanding.');
    const records = await Promise.all(all.map(async row => ({...row,encrypted:!!key,payload:key?await seal(row.payload,key,appId+'/'+row.entity+'/'+row.id):row.payload})));
    await adapter.write({meta:{...state.meta,revision:state.meta.revision+1},records},state.meta.revision);
    return result;
  }
  const storage = {
    adapter: native ? 'SQLite' : 'IndexedDB',
    async init(password='') {
      await adapter.open();
      const state=await adapter.read();
      if (state.meta.salt) {
        if (!password) return {locked:true};
        key=await derive(password,state.meta.salt);
        await unseal(state.meta.verifier,key,appId+'/verify');
      } else if (spec.sensitive_data) {
        if (!password) return {locked:true,initial:true};
        const salt=b64(crypto.getRandomValues(new Uint8Array(16)));
        key=await derive(password,salt);
        state.meta.salt=salt; state.meta.verifier=await seal({valid:true},key,appId+'/verify');
        state.records=await Promise.all(state.records.map(async r=>({...r,encrypted:true,payload:await seal(r.payload,key,appId+'/'+r.entity+'/'+r.id)})));
      }
      compatible(state.meta.schema);
      state.meta.schema={entities:spec.entities};
      state.meta.revision=(state.meta.revision||0)+1;
      await adapter.write(state,state.meta.revision-1);
      return {locked:false};
    },
    async list(name) { entityFor(name); return Promise.all((await adapter.list(name)).map(decode)); },
    async save(name, data, id=null) {
      const entity=entityFor(name);
      return change(all=>{
        const old=id?all.find(r=>r.id===id&&r.entity===name):null;
        if (id && !old) throw Error('Record no longer exists.');
        const row={id:id||crypto.randomUUID(),entity:name,created_at:old?.created_at||new Date().toISOString(),updated_at:new Date().toISOString(),payload:validate(entity,data,all,old)};
        if (old) all.splice(all.indexOf(old),1,row); else all.push(row);
        return row;
      });
    },
    async remove(name,id) {
      entityFor(name);
      return change(all=>{
        const row=all.find(r=>r.id===id&&r.entity===name);
        if (!row) throw Error('Record no longer exists.');
        for (const entity of spec.entities) for (const f of entity.fields) {
          if (f.kind==='reference'&&f.reference===name&&all.some(r=>r.entity===entity.name&&r.payload[f.name]===id)) throw Error('Other records reference this record. Update those relationships before deleting.');
        }
        all.splice(all.indexOf(row),1);
      });
    },
    async transition(name,id,index) {
      const entity=entityFor(name),t=entity.transitions[index];
      if (!t) throw Error('Unknown workflow action.');
      return change(all=>{
        const row=all.find(r=>r.id===id&&r.entity===name);
        if (!row || row.payload[t.field]!==t.from_value) throw Error('This action is not available in the current state.');
        row.payload=validate(entity,{...row.payload,[t.field]:t.to_value},all,row,true);
        row.updated_at=new Date().toISOString();
      });
    },
    async backup(password='') {
      const state=await adapter.read();
      compatible(state.meta.schema);
      if (state.meta.salt&&!key) throw Error('Unlock before exporting.');
      const payload={format:'shift-portable',version:1,application_id:appId,schema:{entities:spec.entities},created_at:new Date().toISOString(),records:await Promise.all(state.records.map(decode))};
      payload.records.forEach(r=>delete r.encrypted);
      if (password) {
        const salt=b64(crypto.getRandomValues(new Uint8Array(16)));
        return JSON.stringify({format:'shift-encrypted',version:1,salt,payload:await seal(payload,await derive(password,salt),'shift-backup-v1')});
      }
      if (spec.sensitive_data || state.meta.salt) throw Error('A backup passphrase is required for sensitive data.');
      return JSON.stringify(payload,null,2);
    },
    async restore(text,password='') {
      if (typeof text!=='string'||text.length>10*1024*1024) throw Error('Choose a backup under 10 MB.');
      let value=JSON.parse(text);
      if (value.format==='shift-encrypted') {
        if (value.version!==1) throw Error('Unsupported encrypted backup version.');
        value=await unseal(value.payload,await derive(password,value.salt),'shift-backup-v1');
      }
      if (value.format!=='shift-portable'||value.version!==1||value.application_id!==appId||!Array.isArray(value.records)||value.records.length>10000) throw Error('This backup belongs to a different application or unsupported format.');
      compatible(value.schema);
      return change(all=>{
        const ids=new Set();
        for (const row of value.records) {
          entityFor(row.entity);
          if (typeof row.id!=='string'||!/^[a-zA-Z0-9-]{8,80}$/.test(row.id)||ids.has(row.id)) throw Error('Invalid or duplicate record ID.');
          ids.add(row.id);
          if (all.some(r=>r.id===row.id&&r.entity!==row.entity)) throw Error('Record identity conflicts with an existing module.');
        }
        const merged=all.filter(r=>!ids.has(r.id)).concat(value.records);
        for (const row of value.records) {
          const entity=entityFor(row.entity);
          if (Object.keys(row.payload||{}).some(k=>!entity.fields.some(f=>f.name===k))) throw Error('Backup has unknown fields. Upgrade the application before importing.');
          row.payload=validate(entity,row.payload,merged,row,true);
          delete row.encrypted;
        }
        all.splice(0,all.length,...merged);
      });
    },
    async persist() { return navigator.storage?.persist ? navigator.storage.persist() : false; },
    async download(text) {
      if (native) return native.invoke('export_backup',{contents:text});
      const url=URL.createObjectURL(new Blob([text],{type:'application/json'}));
      const a=document.createElement('a');a.href=url;a.download='application-backup.json';a.click();
      setTimeout(()=>URL.revokeObjectURL(url),1000);
    }
  };
  window.shiftStorage=storage;
})();
