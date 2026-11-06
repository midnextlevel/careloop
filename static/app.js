// Native dialogs keep focus inside the modal, support Escape, and restore trigger focus.
document.addEventListener('click', event => {
  const trigger = event.target.closest('[data-dialog-open]');
  if (trigger) document.getElementById(trigger.dataset.dialogOpen)?.showModal();
  if (event.target.closest('[data-dialog-close]')) event.target.closest('dialog')?.close();
  if (event.target instanceof HTMLDialogElement) {
    const rect = event.target.getBoundingClientRect();
    if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) event.target.close();
  }
});
document.querySelector('[data-open-on-load]')?.showModal();
// Private text stays solely in the current DOM. No client-side persistence.
if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(() => {});
document.querySelector('[data-go-back]')?.addEventListener('click', () => history.back());
const editor = document.querySelector('[data-editor]');
if (editor) {
  let dirty = false;
  let saving = false;
  let navigating = false;
  let generation = 0;
  const status = document.querySelector('#save-status');
  editor.addEventListener('input', () => { dirty = true; generation++; status.textContent = 'Unsaved changes'; });
  window.addEventListener('beforeunload', event => {
    if (dirty && !navigating) { event.preventDefault(); event.returnValue = ''; }
  });
  editor.addEventListener('submit', async event => {
    if (saving) { event.preventDefault(); return; }
    if (event.submitter?.value === 'review') {
      event.preventDefault();
      saving = true;
      status.textContent = 'Preparing audience review…';
      const reviewedGeneration = generation;
      const data = new FormData(editor);
      data.set('action', 'review');
      const photoFields = editor.querySelector('[data-photo-controls] fieldset');
      if (photoFields) photoFields.disabled = true;
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 20000);
      try {
        const response = await fetch(location.href, {method:'POST', body:data, cache:'no-store', signal:controller.signal});
        const parsed = new DOMParser().parseFromString(await response.text(), 'text/html');
        const review = parsed.querySelector('.review');
        if (!response.ok || !review) throw new Error(parsed.querySelector('.error, .errorlist')?.textContent || 'Review could not be prepared. Check your connection and required fields.');
        if (generation !== reviewedGeneration) throw new Error('Your entry changed while the review was being prepared. Review again to include your latest changes.');
        editor.hidden = true;
        editor.after(review);
        review.scrollIntoView({block:'start'});
        const back = review.querySelector('[data-go-back]');
        back.addEventListener('click', () => {
          if (saving) return;
          review.remove();
          editor.hidden = false;
          status.textContent = 'Unsaved changes — review again before submitting.';
        });
        const confirmForm = review.querySelector('form');
        confirmForm.addEventListener('submit', async confirmEvent => {
          confirmEvent.preventDefault();
          if (saving) return;
          saving = true;
          const button = confirmForm.querySelector('button');
          button.disabled = true;
          back.disabled = true;
          let feedback = review.querySelector('[data-feedback]');
          if (!feedback) { feedback = document.createElement('p'); feedback.dataset.feedback = ''; feedback.setAttribute('role','status'); confirmForm.append(feedback); }
          feedback.textContent = 'Submitting…';
          const submitController = new AbortController();
          const submitTimeout = setTimeout(() => submitController.abort(), 20000);
          try {
            const result = await fetch(confirmForm.action, {method:'POST', body:new FormData(confirmForm), headers:{'Accept':'application/json'}, cache:'no-store', signal:submitController.signal});
            const expectedPath = new URL('../', confirmForm.action).pathname;
            if (!result.ok || result.redirected) throw new Error('Submission was not confirmed. Your session may have expired or a newer version may exist. Go back to edit and open the latest version before retrying.');
            const confirmation = await result.json();
            const destination = new URL(confirmation.redirect_url, location.href);
            if (confirmation.published !== true || destination.origin !== location.origin || ![expectedPath, '/'].includes(destination.pathname)) throw new Error('The server did not confirm submission.');
            dirty = false;
            navigating = true;
            location.assign(destination.href);
          } catch (error) {
            feedback.textContent = `${error.message} Your text remains in this open page. You can retry this confirmation safely.`;
          } finally {
            clearTimeout(submitTimeout);
            if (!navigating) {
              saving = false;
              button.disabled = false;
              back.disabled = false;
            }
          }
        });
      } catch (error) {
        status.textContent = `Review failed. ${error.message} Your text remains in this open page.`;
      } finally { clearTimeout(timeout); saving = false; if (photoFields) photoFields.disabled = false; }
      return;
    }
    if (event.submitter?.value !== 'save') { navigating = true; return; }
    event.preventDefault();
    saving = true;
    const sentGeneration = generation;
    status.textContent = 'Saving…';
    const data = new FormData(editor);
    data.set('action', 'save');
    const photoFields = editor.querySelector('[data-photo-controls] fieldset');
    if (photoFields) photoFields.disabled = true;
    const buttons = [...editor.querySelectorAll('button')];
    buttons.forEach(button => button.disabled = true);
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 20000);
    try {
      const response = await fetch(location.href, {method: 'POST', body: data, headers: {'Accept': 'application/json'}, cache: 'no-store', signal: controller.signal});
      const result = await response.json();
      if (!response.ok) throw new Error([result.error, ...Object.values(result.fields || {}).flat()].filter(Boolean).join(' ') || 'Save was not confirmed.');
      if (result.photos_html) editor.querySelector('[data-photo-controls]').innerHTML = result.photos_html;
      editor.elements.version.value = result.version;
      dirty = generation !== sentGeneration;
      status.textContent = dirty ? 'Unsaved changes made while saving. Save again.' : `Saved on the server at ${result.saved_at}`;
    } catch (error) {
      dirty = true;
      status.textContent = `Save not confirmed. ${error.message} Keep this page open. Review the latest version before retrying if a conflict occurred.`;
    } finally {
      clearTimeout(timeout);
      saving = false;
      buttons.forEach(button => button.disabled = false);
      if (photoFields) photoFields.disabled = false;
    }
  });
  window.addEventListener('offline', () => { status.textContent = dirty ? 'Offline — changes are unsaved. Keep this page open.' : 'Offline — further changes cannot be saved yet.'; });
  window.addEventListener('pageshow', () => { navigating = false; });
}
