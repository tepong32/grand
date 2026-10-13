/* Guided inputs only; the existing server services enforce every source/control. */
(() => {
  'use strict';
  const form = document.getElementById('whole-intake');
  const make = (tag, text, cls) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (cls) node.className = cls;
    return node;
  };
  const button = (label, action) => {
    const node = make('button', label, 'btn btn-outline-secondary me-2 text-nowrap'); node.type = 'button';
    node.addEventListener('click', action); return node;
  };
  function field(root, title, value, change, options, type) {
    const label = make('label', title, 'd-block mb-2');
    const input = make(options ? 'select' : 'input', undefined, 'form-control');
    input.setAttribute('aria-label', title);
    if (options) for (const [key, text] of options) {
      const option = make('option', text); option.value = key; input.append(option);
    }
    if (type) input.type = type;
    input.value = value ?? '';
    input.addEventListener(options ? 'change' : 'input', () => change(input.value));
    label.append(input); root.append(label);
  }
  function pager(root, values, draw, size = 10) {
    let page = 0;
    function render() {
      root.replaceChildren(); const count = Math.max(1, Math.ceil(values.length / size));
      page = Math.min(page, count - 1);
      const nav = make('nav', undefined, 'd-flex flex-wrap gap-2 align-items-center mb-3');
      nav.setAttribute('aria-label', root.id + ' pages');
      const previous = button('Previous', () => {page--; render();}); previous.disabled = page === 0;
      const next = button('Next', () => {page++; render();}); next.disabled = page === count - 1;
      nav.append(previous, make('span', `${values.length} sources · page ${page+1} of ${count}`), next); root.append(nav);
      values.slice(page*size, (page+1)*size).forEach(row => draw(root, row, render));
    }
    render();
  }
  const schemas = {
    cash_changes: [['key','Movement identity'],['source_row','Original worksheet row'],['effective_date','Effective date',null,'date'],
      ['direction','Direction',[['','Choose'],['in','Cash in'],['out','Cash out']]],['amount','Positive amount'],['basis','Source and timing basis']],
    proposed_restrictions: [['key','New restriction identity'],['reference','Original reference'],['purpose','Restriction purpose'],['coverage','Restriction coverage']],
    restriction_changes: [['key','Movement identity'],['source_row','Original worksheet row'],['effective_date','Effective date',null,'date'],
      ['restriction','Exact original / proposed restriction identity'],['action','Movement',[['','Choose'],['add','Add'],['remove','Remove']]],
      ['amount','Positive amount'],['basis','Source and timing basis']]
  };
  for (const root of document.querySelectorAll('.worksheet-rows')) {
    const input = document.getElementById(root.dataset.input); const schema = schemas[root.dataset.kind];
    let rows;
    try { rows = JSON.parse(input.value || '[]') ?? []; } catch { root.append(make('p','Invalid submitted worksheet. Reload the source.')); continue; }
    if (!Array.isArray(rows) || rows.some(row => !row || typeof row !== 'object' || Array.isArray(row))) {
      root.append(make('p','Invalid submitted worksheet. Reload the source.')); continue;
    }
    const sync = () => { input.value = JSON.stringify(rows); };
    function render() {
      root.replaceChildren(); root.append(make('h3', root.dataset.kind.replaceAll('_',' '), 'h6'));
      rows.forEach(row => {
        const card = make('div', undefined, 'border p-2 mb-2');
        schema.forEach(([key,title,options,type]) => field(card,title,row[key], value => {row[key]=value; sync();},options,type));
        card.append(button('Remove worksheet row', () => {rows.splice(rows.indexOf(row),1); sync(); render();})); root.append(card);
      });
      root.append(button('Add explicit worksheet row', () => {rows.push(Object.fromEntries(schema.map(([key]) => [key,'']))); sync(); render();}));
    }
    sync(); render(); form.addEventListener('submit',sync);
  }
  const retained = document.getElementById('whole-editor-data'); if (!retained) return;
  const data = JSON.parse(retained.textContent);
  const parts = data.parts ?? data.catalog.map((row,index) => ({key:`ph-${index+1}`, source:row.key,
    amount:row.amount, treatment:'unresolved', counterpart:'', basis:''}));
  const coverage = data.coverage ?? data.matrix.map(row => ({entity:row.entity,column:row.column,kind:row.kind,coverage:'missing',basis:''}));
  if (!Array.isArray(parts) || !Array.isArray(coverage) || [...parts,...coverage].some(row => !row || typeof row !== 'object' || Array.isArray(row))) {
    document.getElementById('whole-parts').append(make('p','Invalid submitted partitions. Preview original sources again.')); return;
  }
  const sync = () => {
    document.getElementById('id_parts').value = JSON.stringify(parts);
    document.getElementById('id_coverage').value = JSON.stringify(coverage);
  };
  const titles = {deduct:'Deduct',claimed_overlap:'Explicit overlap claim',unresolved:'Unresolved',
    philhealth_carryover:'PhilHealth carryover',other:'Other funding / restriction',shf:'SHF funding',counterpart:'Counterpart funding'};
  let keyNumber = 1;
  pager(document.getElementById('whole-parts'), data.catalog, (root, source, render) => {
    const card = make('section',undefined,'card card-body mb-3');
    card.append(make('h3',`${source.entity_label} · ${source.column_label} · ${source.kind}`,'h5'));
    card.append(make('p',`${source.amount} · ${source.label}`));
    const counterparts = [['','Choose exact original counterpart'], ...data.catalog.filter(row => row.entity===source.entity && row.kind!=='receipt')
      .map(row => [row.key,`${row.column_label} · ${row.kind} · ${row.amount} · ${row.label}`])];
    for (const part of parts.filter(row => row.source===source.key)) {
      const box = make('div',undefined,'border p-2 mb-2');
      field(box,'Signed amount',part.amount,value => {part.amount=value; sync();});
      field(box,'Treatment',part.treatment,value => {part.treatment=value; if (value!=='claimed_overlap') part.counterpart=''; sync(); render();},
        [['unresolved',titles.unresolved],...data.treatments[source.kind].filter(value => value!=='unresolved').map(value => [value,titles[value]])]);
      if (part.treatment==='claimed_overlap') field(box,'Original counterpart',part.counterpart,value => {part.counterpart=value; sync();},counterparts);
      field(box,'Original source / funding / overlap basis',part.basis,value => {part.basis=value; sync();});
      box.append(button('Remove part',() => {parts.splice(parts.indexOf(part),1); sync(); render();})); card.append(box);
    }
    card.append(button('Add explicit split part',() => {
      let key; do {key=`ph-added-${keyNumber++}`;} while (parts.some(part => part.key===key));
      parts.push({key,source:source.key,amount:'',treatment:'unresolved',counterpart:'',basis:''}); sync(); render();
    })); root.append(card);
  });
  pager(document.getElementById('whole-coverage'),data.matrix,(root,cell) => {
    const row = coverage.find(item => item.entity===cell.entity && item.column===cell.column && item.kind===cell.kind);
    const card = make('section',undefined,'card card-body mb-2');
    card.append(make('h3',`${cell.entity_label} · ${cell.column_label} · ${cell.kind}`,'h6'));
    if (!row) card.append(make('p','Missing submitted cell. Preview the original source again.'));
    else {
      field(card,'Coverage',row.coverage,value => {row.coverage=value; sync();},[['missing','Missing evidence'],['complete','Complete with evidence']]);
      field(card,'Whole source coverage / non-overlap basis',row.basis,value => {row.basis=value; sync();});
    }
    root.append(card);
  },12);
  sync(); form.addEventListener('submit',sync);
})();
