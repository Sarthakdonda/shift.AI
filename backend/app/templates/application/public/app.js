'use strict';
const $ = (id) => document.getElementById(id);
let spec, selected, offset = 0;
const el = (tag, text, parent) => { const node = document.createElement(tag); if (text !== undefined) node.textContent = text; if (parent) parent.append(node); return node; };
async function request(path, body, method) {
  const response = await fetch(path, { method: method || (body ? 'POST' : 'GET'), headers: body ? { 'Content-Type': 'application/json' } : {}, body: body ? JSON.stringify(body) : undefined });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Request failed.');
  return data;
}
function notice(error) { $('notice').textContent = error.message || error; }
async function task(button, operation) { button.disabled = true; try { await operation(); notice(''); } catch (error) { notice(error); } finally { button.disabled = false; } }
$('login-form').onsubmit = (event) => { event.preventDefault(); const button = event.target.querySelector('button'); task(button, async () => { await request('/api/login', Object.fromEntries(new FormData(event.target))); event.target.reset(); await start(); }); };
$('logout').onclick = () => task($('logout'), async () => { await request('/api/logout', {}); location.reload(); });
async function start() {
  spec = await request('/api/spec');
  document.documentElement.lang = spec.language;
  document.documentElement.dir = /^(ar|he|ur|fa)(-|$)/.test(spec.language) ? 'rtl' : 'ltr';
  document.title = spec.name; $('title').textContent = spec.name; $('description').textContent = spec.description;
  $('login').hidden = true; $('workspace').hidden = false; $('logout').hidden = false;
  $('navigation').replaceChildren();
  for (const entity of spec.entities) { const button = el('button', entity.label, $('navigation')); button.onclick = () => { selected = entity; offset = 0; show().catch(notice); }; }
  if (spec.user.role === 'admin') { const button = el('button', 'Team accounts', $('navigation')); button.onclick = () => users().catch(notice); }
  selected = spec.entities[0]; if (selected) await show();
}
async function show(query = '') {
  const entity = selected;
  const rows = await request('/api/records/' + entity.name + '?q=' + encodeURIComponent(query) + '&offset=' + offset);
  $('module').replaceChildren(); el('h2', entity.label, $('module'));
  const toolbar = el('div', undefined, $('module')); toolbar.className = 'toolbar';
  const search = el('input', undefined, toolbar); search.type = 'search'; search.placeholder = 'Search records'; search.setAttribute('aria-label', 'Search records'); search.value = query;
  const searchButton = el('button', 'Search', toolbar); searchButton.onclick = () => task(searchButton, async () => { offset = 0; await show(search.value); });
  const writable = spec.user.role === 'admin' || entity.write_roles.includes(spec.user.role);
  if (writable) { const add = el('button', 'Add record', toolbar); add.onclick = () => editor(entity).catch(notice); }
  if (!rows.length) el('p', 'No records yet. Add a record or try another search.', $('module')).className = 'empty';
  else {
    const wrap = el('div', undefined, $('module')); wrap.className = 'table-wrap';
    const table = el('table', undefined, wrap), head = el('tr', undefined, el('thead', undefined, table));
    for (const field of entity.fields) el('th', field.label, head);
    if (writable) el('th', 'Actions', head);
    const body = el('tbody', undefined, table);
    for (const row of rows) {
      const tr = el('tr', undefined, body);
      for (const field of entity.fields) el('td', field.kind === 'boolean' ? (row[field.name] ? 'Yes' : 'No') : String(row[field.name] ?? '—'), tr);
      if (writable) {
        const cell = el('td', undefined, tr); const edit = el('button', 'Edit', cell); edit.onclick = () => editor(entity, row).catch(notice);
        const remove = el('button', 'Delete', cell); remove.onclick = () => { if (confirm('Delete this record? This cannot be undone.')) task(remove, async () => { await request('/api/records/' + entity.name + '/' + row.id, undefined, 'DELETE'); await show(query); }); };
        entity.transitions.forEach((transition, index) => { if (row[transition.field] === transition.from_value && (spec.user.role === 'admin' || transition.roles.includes(spec.user.role))) { const action = el('button', transition.label, cell); action.onclick = () => task(action, async () => { await request('/api/records/' + entity.name + '/' + row.id + '/transition', { transition: index }); await show(query); }); } });
      }
    }
  }
  const paging = el('div', undefined, $('module')); paging.className = 'toolbar';
  if (offset) { const previous = el('button', 'Previous', paging); previous.onclick = () => { offset -= 100; show(query).catch(notice); }; }
  if (rows.length === 100) { const next = el('button', 'Next', paging); next.onclick = () => { offset += 100; show(query).catch(notice); }; }
}
async function editor(entity, row) {
  const dialog = el('dialog', undefined, document.body); el('h2', row ? 'Edit record' : 'Add record', dialog);
  const form = el('form', undefined, dialog), inputs = {};
  const errorBox = el('p', '', form); errorBox.setAttribute('role', 'alert');
  try {
    for (const field of entity.fields) {
      const label = el('label', field.label, form);
      const input = el(field.kind === 'select' || field.kind === 'reference' ? 'select' : 'input', undefined, label);
      input.setAttribute('aria-label', field.label);
      if (field.kind === 'select') { if (!field.required) el('option', '', input).value = ''; field.options.forEach(value => el('option', value, input).value = value); }
      else if (field.kind === 'reference') {
        el('option', 'Choose a record', input).value = '';
        const target = spec.entities.find(e => e.name === field.reference);
        if (!target) throw new Error('Your role needs read access to ' + field.reference + ' to select related records.');
        const records = await request('/api/records/' + field.reference);
        records.forEach(record => el('option', String(record[target.fields[0].name] || record.id), input).value = record.id);
      } else { input.type = { boolean: 'checkbox', number: 'number', date: 'date', email: 'email' }[field.kind] || 'text'; if (field.kind === 'number') input.step = 'any'; }
      input.name = field.name; input.required = field.required && field.kind !== 'boolean';
      if (field.kind === 'boolean') input.checked = Boolean(row?.[field.name]); else input.value = row?.[field.name] ?? (entity.transitions.some(t => t.field === field.name) ? field.options[0] : '');
      if (entity.transitions.some(t => t.field === field.name)) input.disabled = true;
      inputs[field.name] = input;
    }
    const actions = el('div', undefined, form); actions.className = 'actions';
    const save = el('button', 'Save record', actions); save.type = 'submit';
    const cancel = el('button', 'Cancel', actions); cancel.type = 'button'; cancel.onclick = () => dialog.close();
    form.onsubmit = async event => { event.preventDefault(); save.disabled = true; try {
      const values = {}; for (const field of entity.fields) { const input = inputs[field.name]; values[field.name] = field.kind === 'boolean' ? input.checked : field.kind === 'number' && input.value !== '' ? Number(input.value) : input.value; }
      await request('/api/records/' + entity.name + (row ? '/' + row.id : ''), values); dialog.close(); await show();
    } catch (error) { errorBox.textContent = error.message; } finally { save.disabled = false; } };
    dialog.onclose = () => dialog.remove(); dialog.showModal();
  } catch (error) { dialog.remove(); throw error; }
}
async function users() {
  $('module').replaceChildren(); el('h2', 'Team accounts', $('module'));
  const accounts = await request('/api/users'); accounts.forEach(a => el('p', a.email + ' · ' + a.role, $('module')));
  const form = el('form', undefined, $('module'));
  for (const name of ['email', 'password']) { const label = el('label', name === 'email' ? 'Email' : 'Initial password (12+ characters)', form), input = el('input', undefined, label); input.name = name; input.type = name; input.required = true; if (name === 'password') { input.minLength = 12; input.autocomplete = 'new-password'; } }
  const roles = el('select', undefined, el('label', 'Role', form)); roles.name = 'role'; roles.setAttribute('aria-label', 'Role'); spec.roles.forEach(role => el('option', role, roles).value = role);
  const save = el('button', 'Create account', form); form.onsubmit = event => { event.preventDefault(); task(save, async () => { await request('/api/users', Object.fromEntries(new FormData(form))); await users(); }); };
}
start().catch(error => { if (error.message !== 'Please sign in.') notice(error); });
