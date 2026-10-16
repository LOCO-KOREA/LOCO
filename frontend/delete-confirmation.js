// One modal owns the confirmed target until the service finishes deleting it.
export function createDeleteConfirmation(document) {
  let active = false;
  return async function confirmDeletion({title, message, remove}) {
    if (active) return false;
    active = true;
    let dialog;
    try {
      dialog = document.createElement('dialog');
      dialog.className = 'delete-confirmation';
      dialog.setAttribute('aria-labelledby', 'delete-confirmation-title');
      dialog.setAttribute('aria-describedby', 'delete-confirmation-message');
      dialog.innerHTML = '<h2 id="delete-confirmation-title"></h2><p id="delete-confirmation-message"></p><p class="delete-status" role="status"></p><div class="delete-actions"><button type="button" data-cancel autofocus>취소</button><button type="button" data-confirm class="danger">삭제</button></div>';
      dialog.querySelector('h2').textContent = title;
      dialog.querySelector('#delete-confirmation-message').textContent = message;
      const cancel = dialog.querySelector('[data-cancel]');
      const confirm = dialog.querySelector('[data-confirm]');
      let deleting = false;
      const result = new Promise((resolve, reject) => {
        cancel.addEventListener('click', () => { if (!deleting) resolve(false); });
        dialog.addEventListener('cancel', event => {
          event.preventDefault();
          if (!deleting) resolve(false);
        });
        confirm.addEventListener('click', async () => {
          if (deleting) return;
          deleting = true;
          cancel.disabled = confirm.disabled = true;
          dialog.setAttribute('aria-busy', 'true');
          dialog.querySelector('.delete-status').textContent = '삭제 중입니다. 잠시 기다려 주세요.';
          try { await remove(); resolve(true); }
          catch (error) { reject(error); }
        });
      });
      document.body.append(dialog);
      dialog.showModal();
      cancel.focus();
      return await result;
    } finally {
      if (dialog?.open) dialog.close();
      dialog?.remove();
      active = false;
    }
  };
}
