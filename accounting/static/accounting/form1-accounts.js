(() => {
  'use strict';
  const root = document.getElementById('account-editor');
  if (!root) return;
  const data = JSON.parse(document.getElementById('account-editor-data').textContent);
  const output = document.getElementById('id_allocation');
  let state = data.allocation || data.components.map((source, index) => ({key: `part-${index}`,
    component: source.key, amount: source.amount, disposition: 'unresolved', account_id: '', basis: ''}));
  let page = 1, search = '', serial = 0;
  const el = (tag, text, cls) => { const node = document.createElement(tag); if (text !== undefined) node.textContent = text; if (cls) node.className = cls; return node; };
  const save = () => { output.value = JSON.stringify(state); };
  const button = (text, action) => { const node = el('button', text, 'btn btn-outline-secondary mr-2 mb-2'); node.type = 'button'; node.addEventListener('click', action); return node; };
  const cents = value => { const match = /^(-?)(\d+)(?:\.(\d{1,2}))?$/.exec(String(value)); return match ? (match[1] ? -1n : 1n) * (BigInt(match[2])*100n + BigInt((match[3] || '').padEnd(2,'0'))) : null; };
  const money = value => `${value < 0n ? '-' : ''}${(value < 0n ? -value : value)/100n}.${String((value < 0n ? -value : value)%100n).padStart(2,'0')}`;
  function field(parent, label, row, key, options) {
    const wrap = el('label', undefined, 'd-block mb-2'); wrap.append(el('span', label));
    const input = el(options ? 'select' : key === 'basis' ? 'textarea' : 'input'); input.className = 'form-control';
    if (options) for (const choice of options) { const option = el('option', choice.label); option.value = choice.id; input.append(option); }
    if (key === 'basis') { input.rows = 2; input.maxLength = 2000; }
    if (key === 'amount') input.inputMode = 'decimal';
    input.dataset.field=key; input.value = row[key] == null ? '' : row[key];
    input.addEventListener('input', () => {
      row[key] = input.value;
      if (key==='disposition' && row[key]==='unresolved') { row.account_id=''; parent.querySelector('[data-field="account_id"]').value=''; }
      save(); updateTotal(parent.closest('section'));
    });
    wrap.append(input); parent.append(wrap);
  }
  function updateTotal(card) {
    const parts = state.filter(row => row.component === card.dataset.component);
    const values = parts.map(row => cents(row.amount)); const target = cents(card.dataset.amount);
    const summary = card.querySelector('[data-total]');
    if (values.some(value => value === null)) { summary.textContent = 'Enter each signed amount with at most two decimal places.'; return; }
    const total = values.reduce((sum, value) => sum+value, 0n);
    summary.textContent = `Allocated ${money(total)} · remaining ${money(target-total)}${total === target ? ' · exact total' : ''}`;
  }
  function render() {
    root.replaceChildren();
    const filter = el('label', undefined, 'd-block'); filter.append(el('span','Search entity, category, period or original account'));
    const input = el('input'); input.className='form-control'; input.value=search;
    input.addEventListener('change', () => { search=input.value; page=1; render(); }); filter.append(input); root.append(filter);
    const filtered = data.components.filter(source => [source.entity,source.category_label,source.column,source.period,source.source_label,source.source_account_label].join(' ').toLowerCase().includes(search.toLowerCase()));
    const pages = Math.max(1,Math.ceil(filtered.length/10)); page=Math.min(page,pages);
    root.append(el('p',`${data.components.length} original components retained · ${filtered.length} match · page ${page} of ${pages}. Choices on other pages are preserved.`));
    for (const source of filtered.slice((page-1)*10,page*10)) {
      const card=el('section',undefined,'card card-body mb-3'); card.dataset.component=source.key; card.dataset.amount=source.amount;
      card.style.overflowWrap='anywhere';
      card.append(el('h2',`${source.entity} · ${source.kind} · ${source.category_label}`,'h5'));
      card.append(el('p',`${source.column} · ${source.period} · original signed amount ${source.amount}`));
      card.append(el('p',`${source.source_label} · Original source account: ${source.source_account_label}`));
      const options=[{id:'',label: source.source_account===null && cents(source.amount)===0n ? 'Original explicit zero without an account' : 'Choose a valid coded reporting account'},
        ...data.accounts.filter(account => source.eligible_accounts.includes(account.id))];
      if (options.length===1 && !(source.source_account===null && cents(source.amount)===0n)) card.append(el('p','No captured coded account covers this source period. Keep the amount unresolved; a reviewed successor chart/forecast may be needed.','text-warning'));
      for (const row of state.filter(part => part.component===source.key)) {
        const part=el('div',undefined,'border rounded p-2 mb-2');
        field(part,'Signed amount',row,'amount');
        field(part,'Selection',row,'disposition',[{id:'unresolved',label:'Unresolved — retain a basis'},{id:'mapped',label:'Explicit reporting selection'}]);
        field(part,'Reporting account (government code · title · local code)',row,'account_id',options);
        field(part,'Selection or unresolved basis',row,'basis');
        if (state.filter(item => item.component===source.key).length>1) part.append(button('Remove split',() => { state=state.filter(item=>item!==row); save(); render(); }));
        card.append(part);
      }
      const total=el('p'); total.dataset.total=''; total.setAttribute('aria-live','polite'); card.append(total);
      if (cents(source.amount)!==0n) card.append(button('Add split',() => {
        state.push({key:`part-${Date.now()}-${++serial}`,component:source.key,amount:'',disposition:'unresolved',account_id:'',basis:''}); save(); render();
      }));
      root.append(card); updateTotal(card);
    }
    if (!filtered.length) root.append(el('p','No component matches this search. All original choices remain in the package.'));
    const nav=el('nav'); nav.setAttribute('aria-label','Source component pages');
    if (page>1) nav.append(button('Previous sources',()=>{page--;render();}));
    if (page<pages) nav.append(button('Next sources',()=>{page++;render();}));
    root.append(nav); save();
  }
  document.getElementById('account-intake').addEventListener('submit',save);
  render();
})();
