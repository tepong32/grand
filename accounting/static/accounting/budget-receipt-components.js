(() => {
  const form = document.getElementById('receipt-components-form');
  const container = document.getElementById('receipt-components');
  if (!form || !container) return;
  const enable = row => row.querySelectorAll('[data-component-field]').forEach(input => input.removeAttribute('name'));
  container.querySelectorAll('.receipt-component').forEach(enable);
  let sequence = container.children.length;
  document.getElementById('receipt-add-component').addEventListener('click', () => {
    const fragment = document.getElementById('receipt-component-template').content.cloneNode(true);
    fragment.querySelectorAll('[id], [for]').forEach(element => {
      for (const key of ['id', 'for']) {
        if (element.hasAttribute(key)) element.setAttribute(key, element.getAttribute(key).replace('__prefix__', sequence));
      }
    });
    const row = fragment.querySelector('.receipt-component');
    enable(row); container.append(fragment); sequence += 1;
    row.querySelector('select').focus();
  });
  container.addEventListener('click', event => {
    const remove = event.target.closest('[data-remove-component]');
    if (remove) remove.closest('.receipt-component').remove();
  });
  form.addEventListener('submit', () => {
    const rows = Array.from(container.querySelectorAll('.receipt-component'), row =>
      Object.fromEntries(Array.from(row.querySelectorAll('[data-component-field]'), input =>
        [input.dataset.componentField, input.value])));
    form.querySelector('[name="rows"]').value = JSON.stringify(rows);
  });
  document.getElementById('receipt-submit').disabled = false;
})();
