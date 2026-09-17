/* Personal Vault — shared interactions
 *
 * Vanilla JS, no dependencies, no build step. Behaviour hangs off
 * data-attributes through event delegation, so templates never carry
 * inline script and a strict Content-Security-Policy keeps working.
 *
 * Blocks marked MOCKUP ONLY fake a server round-trip and are replaced by
 * real requests in the build stages.
 */
(() => {
  'use strict';

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const pointerFine = window.matchMedia('(hover: hover) and (pointer: fine)');
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  // The real app marks <body data-app>; the static mockups don't. MOCKUP ONLY fakes
  // must never run inside the app.
  const IS_APP = 'app' in document.body.dataset;

  const MAX_UPLOAD_BYTES = 2 * 1024 ** 3;
  const COPY_FALLBACK_MESSAGE =
    'Press and hold to copy — open the vault over HTTPS for one-tap copy.';

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function icon(name, extra = '') {
    const node = el('span', `icon icon--${name} ${extra}`.trim());
    node.setAttribute('aria-hidden', 'true');
    return node;
  }

  function iconButton(name, label) {
    const button = el('button', 'icon-btn');
    button.type = 'button';
    button.setAttribute('aria-label', label);
    button.append(icon(name));
    return button;
  }

  /* ---- Toast ---------------------------------------------------------- */
  /* One at a time; a new one replaces the old. */

  let toastTimer;

  function toast(message, { error = false } = {}) {
    const box = $('.toast');
    if (!box) return;
    $('.toast__text', box).textContent = message;
    $('.toast__icon', box).className =
      `icon icon--sm toast__icon icon--${error ? 'circle-alert' : 'check'}`;
    box.classList.add('is-visible');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => box.classList.remove('is-visible'), error ? 4000 : 2000);
  }

  /* ---- Copy ----------------------------------------------------------- */

  async function writeClipboard(text) {
    if (window.isSecureContext && navigator.clipboard) {
      try {
        await navigator.clipboard.writeText(text);
        return true;
      } catch {
        /* fall through to the legacy path */
      }
    }
    // Plain http has no async Clipboard API, but execCommand('copy') still
    // works inside a tap. Copy from an off-screen textarea, then put focus
    // back where it was.
    const previousFocus = document.activeElement;
    const scratch = el('textarea', 'copy-scratch');
    scratch.value = text;
    scratch.setAttribute('readonly', '');
    document.body.append(scratch);
    scratch.select();
    scratch.setSelectionRange(0, text.length);
    let ok = false;
    try {
      ok = document.execCommand('copy');
    } catch {
      ok = false;
    }
    scratch.remove();
    if (previousFocus instanceof HTMLElement) previousFocus.focus({ preventScroll: true });
    return ok;
  }

  function copySource(trigger) {
    if (!trigger) return '';
    if (trigger.dataset.copy) return trigger.dataset.copy;
    if (trigger.dataset.copyFrom) {
      const source = $(trigger.dataset.copyFrom);
      if (!source) return '';
      return 'value' in source ? source.value : source.textContent;
    }
    // A clip always copies .clip__source — the whole text, never the
    // preview that is visible on screen.
    const clip = trigger.closest('.clip');
    return clip ? $('.clip__source', clip).value : '';
  }

  const copiedTimers = new WeakMap();

  async function copy(trigger, text) {
    const ok = await writeClipboard(text);
    if (!ok) {
      toast(COPY_FALLBACK_MESSAGE, { error: true });
      return;
    }
    toast('Copied ✓');
    if (!trigger.classList.contains('copy-btn')) return;
    const label = $('.copy-btn__label', trigger);
    trigger.classList.add('is-copied');
    label.textContent = 'Copied ✓';
    clearTimeout(copiedTimers.get(trigger));
    copiedTimers.set(trigger, setTimeout(() => {
      trigger.classList.remove('is-copied');
      label.textContent = 'COPY';
    }, 1500));
  }

  /* ---- Hidden clips and favourite stars ------------------------------- */

  function setRevealed(button, show) {
    const clip = button.closest('.clip');
    button.setAttribute('aria-pressed', String(show));
    button.setAttribute('aria-label', `${show ? 'Hide' : 'Show'} ${button.dataset.name || ''}`.trim());
    $('.clip__masked', clip).hidden = show;
    $('.clip__content', clip).hidden = !show;
  }

  function toggleStar(button) {
    const on = button.getAttribute('aria-pressed') !== 'true';
    button.setAttribute('aria-pressed', String(on));
    button.setAttribute('aria-label', `${on ? 'Unfavorite' : 'Favorite'} ${button.dataset.name || ''}`.trim());
  }

  // Revealed clips hide again when the page is returned to from history.
  window.addEventListener('pageshow', (event) => {
    if (!event.persisted) return;
    $$('[data-reveal][aria-pressed="true"]').forEach((button) => setRevealed(button, false));
  });

  /* ---- Sheets, popovers and the delete confirm ------------------------ */

  let sheetTrigger = null;

  function openSheet(trigger) {
    const dialog = document.getElementById(trigger.dataset.sheetOpen);
    if (!dialog) return;
    sheetTrigger = trigger;
    const title = $('.sheet__title', dialog);
    if (title && trigger.dataset.sheetTitle) title.textContent = trigger.dataset.sheetTitle;
    // Toggle actions say what they will do to this item, not what they did last.
    const favorite = $('[data-action="favorite"]', dialog);
    if (favorite) favorite.lastChild.textContent = 'favorite' in trigger.dataset ? 'Unfavorite' : 'Favorite';
    const hide = $('[data-action="hide"]', dialog);
    if (hide) hide.lastChild.textContent = 'clipHidden' in trigger.dataset ? 'Unhide content' : 'Hide content';
    const popover = pointerFine.matches && !trigger.closest('.tabbar');
    dialog.classList.toggle('sheet--popover', popover);
    dialog.style.top = '';
    dialog.style.left = '';
    dialog.showModal();
    if (popover) placePopover(dialog, trigger);
  }

  // CSSOM writes like this are allowed under a CSP that forbids style="".
  function placePopover(dialog, trigger) {
    const gap = 4;
    const margin = 8;
    const anchor = trigger.getBoundingClientRect();
    const width = dialog.offsetWidth;
    const height = dialog.offsetHeight;
    const left = Math.max(margin, Math.min(anchor.right - width, window.innerWidth - width - margin));
    let top = anchor.bottom + gap;
    if (top + height > window.innerHeight - margin) top = Math.max(margin, anchor.top - height - gap);
    dialog.style.left = `${left}px`;
    dialog.style.top = `${top}px`;
  }

  function closeIfBackdrop(event) {
    const dialog = event.target;
    const box = dialog.getBoundingClientRect();
    const inside = event.clientX >= box.left && event.clientX <= box.right
      && event.clientY >= box.top && event.clientY <= box.bottom;
    if (!inside) dialog.close();
  }

  function confirmDelete(name) {
    const modal = document.getElementById('modal-delete');
    if (!modal) return;
    $('.modal__title', modal).textContent = `Delete ${name}?`;
    modal.showModal();
  }

  function runAction(item) {
    const dialog = item.closest('dialog');
    const name = sheetTrigger?.dataset.sheetTitle
      || (dialog && $('.sheet__title', dialog)?.textContent)
      || 'this item';
    dialog?.close();
    switch (item.dataset.action) {
      case 'toast':
        toast(item.dataset.toast);
        break;
      case 'copy':
        copy(item, copySource(item.dataset.copyFrom ? item : sheetTrigger));
        break;
      case 'favorite':
        // MOCKUP ONLY: S9 sends the favorite toggle here.
        toast(sheetTrigger && 'favorite' in sheetTrigger.dataset ? 'Removed from Favorites' : 'Added to Favorites');
        break;
      case 'hide':
        // MOCKUP ONLY: S4 sends the hide toggle here.
        toast(sheetTrigger && 'clipHidden' in sheetTrigger.dataset ? 'Content no longer hidden' : 'Content hidden');
        break;
      case 'delete':
        confirmDelete(name);
        break;
      case 'confirm-delete':
        // MOCKUP ONLY: S5/S6 send the delete request here.
        toast('Deleted');
        break;
      default:
        break;
    }
  }

  /* ---- Filter chips --------------------------------------------------- */

  function pressChip(chip) {
    const group = chip.closest('.chips');
    $$('.chip', group).forEach((other) => other.setAttribute('aria-pressed', String(other === chip)));
    const listId = group.dataset.filter;
    const list = listId && document.getElementById(listId);
    if (!list) return;
    const value = chip.dataset.value;
    let shown = 0;
    $$('[data-type]', list).forEach((item) => {
      const match = value === 'all' || item.dataset.type === value;
      item.hidden = !match;
      if (match) shown += 1;
    });
    const empty = document.getElementById(`${listId}-empty`);
    if (empty) empty.hidden = shown > 0;
  }

  /* ---- Upload panel --------------------------------------------------- */

  const STATUS_ICON = {
    waiting: 'file',
    uploading: 'loader-circle',
    done: 'check',
    failed: 'circle-alert',
  };

  const uploadInput = el('input');
  uploadInput.type = 'file';
  uploadInput.multiple = true;
  uploadInput.hidden = true;
  document.body.append(uploadInput);

  uploadInput.addEventListener('change', () => {
    addUploads(Array.from(uploadInput.files));
    uploadInput.value = '';
  });

  function formatSize(bytes) {
    const units = ['B', 'KB', 'MB', 'GB'];
    let value = bytes;
    let unit = 0;
    while (value >= 1024 && unit < units.length - 1) {
      value /= 1024;
      unit += 1;
    }
    return `${unit === 0 ? value : value.toFixed(value < 10 ? 1 : 0)} ${units[unit]}`;
  }

  // Same split as the templates: the last 8 characters never truncate.
  function nameNode(name, extra) {
    const cut = Math.max(0, name.length - 8);
    const node = el('span', `name ${extra}`);
    node.append(el('span', 'name__head', name.slice(0, cut)), el('span', 'name__tail', name.slice(cut)));
    return node;
  }

  function uploadPanel() {
    let panel = document.getElementById('upload-panel');
    if (panel) return panel;
    panel = el('section', 'upload-panel');
    panel.id = 'upload-panel';
    panel.setAttribute('aria-label', 'Uploads');
    const head = el('div', 'upload-panel__head');
    const title = el('h2', 'upload-panel__title');
    title.dataset.uploadTitle = '';
    const toggle = iconButton('chevron-down', 'Collapse uploads');
    toggle.classList.add('upload-panel__toggle');
    toggle.dataset.uploadToggle = '';
    toggle.setAttribute('aria-expanded', 'true');
    const dismiss = iconButton('x', 'Dismiss uploads');
    dismiss.dataset.uploadDismiss = '';
    dismiss.hidden = true;
    head.append(title, toggle, dismiss);
    const list = el('ul', 'upload-panel__list');
    list.dataset.uploadList = '';
    panel.append(head, list);
    document.body.append(panel);
    return panel;
  }

  function uploadRow(file) {
    const row = el('li', 'upload-row');
    Object.assign(row.dataset, {
      name: file.name, size: String(file.size), state: 'waiting', progress: '0',
    });
    if (file.size > MAX_UPLOAD_BYTES) {
      Object.assign(row.dataset, { state: 'failed', error: 'Too large (max 2 GB)', final: 'true' });
    }
    const line = el('div', 'upload-row__line');
    line.append(nameNode(file.name, 'upload-row__name'), el('span', 'upload-row__size', formatSize(file.size)));
    const bar = el('progress', 'progress');
    bar.max = 100;
    const body = el('div', 'upload-row__body');
    body.append(line, bar, el('span', 'upload-row__note'));
    row.append(icon('file', 'icon--sm upload-row__status'), body, el('div', 'upload-row__action'));
    renderRow(row);
    return row;
  }

  function renderRow(row) {
    const { state = 'waiting', progress = '0', error = '', name = '' } = row.dataset;
    $('.upload-row__status', row).className =
      `icon icon--sm icon--${STATUS_ICON[state]} upload-row__status upload-row__status--${state}`
      + (state === 'uploading' ? ' icon--spin' : '');
    const bar = $('.progress', row);
    bar.hidden = state !== 'uploading';
    bar.value = Number(progress);
    const note = $('.upload-row__note', row);
    note.textContent = { waiting: 'Waiting', uploading: `${progress}%`, done: 'Uploaded', failed: error }[state];
    note.classList.toggle('upload-row__note--error', state === 'failed');
    const action = $('.upload-row__action', row);
    action.replaceChildren();
    if (state === 'waiting' || state === 'uploading') {
      const cancel = iconButton('x', `Cancel ${name}`);
      cancel.dataset.uploadCancel = '';
      action.append(cancel);
    } else if (state === 'failed' && row.dataset.final !== 'true') {
      const retry = el('button', 'btn btn--ghost', 'Retry');
      retry.type = 'button';
      retry.dataset.uploadRetry = '';
      action.append(retry);
    }
  }

  function updateUploadTitle() {
    const panel = document.getElementById('upload-panel');
    if (!panel) return;
    const rows = $$('.upload-row', panel);
    const count = (state) => rows.filter((row) => row.dataset.state === state).length;
    const active = count('uploading') + count('waiting');
    const failed = count('failed');
    let title = 'All uploaded';
    if (active) title = `Uploading ${rows.length - active + 1} of ${rows.length}`;
    else if (failed) title = `${failed} failed`;
    $('[data-upload-title]', panel).textContent = title;
    $('[data-upload-dismiss]', panel).hidden = active > 0;
  }

  let uploading = false;
  let autoHideTimer;

  function addUploads(files) {
    if (!files.length) return;
    const panel = uploadPanel();
    panel.hidden = false;
    clearTimeout(autoHideTimer);
    const list = $('[data-upload-list]', panel);
    files.forEach((file) => list.append(uploadRow(file)));
    updateUploadTitle();
    pump();
  }

  function pump() {
    if (uploading) return;
    // Finish the row already uploading before starting the next waiting one,
    // so only one file ever uploads at a time.
    const rows = $$('.upload-row');
    const next = rows.find((row) => row.dataset.state === 'uploading')
      || rows.find((row) => row.dataset.state === 'waiting');
    updateUploadTitle();
    if (!next) return;
    uploading = true;
    next.dataset.state = 'uploading';
    renderRow(next);
    updateUploadTitle();
    simulateUpload(next, () => {
      uploading = false;
      pump();
      if (!uploading) uploadsSettled();
    });
  }

  function uploadsSettled() {
    const rows = $$('.upload-row');
    if (!rows.length) {
      dismissUploads();
      return;
    }
    if (rows.some((row) => row.dataset.state === 'failed')) return; // stays put
    // No "Uploaded" toast: the panel title already says "All uploaded", and a
    // toast would land on top of the panel.
    autoHideTimer = setTimeout(dismissUploads, 4000);
  }

  function dismissUploads() {
    const panel = document.getElementById('upload-panel');
    if (!panel) return;
    panel.hidden = true;
    $('[data-upload-list]', panel).replaceChildren();
  }

  /* MOCKUP ONLY — fake progress so the panel can be reviewed on a phone.
     S6 replaces this with a real XMLHttpRequest and upload.onprogress. */
  function simulateUpload(row, done) {
    const step = Math.max(2, Math.min(25, 4e8 / Number(row.dataset.size || 1)));
    const timer = setInterval(() => {
      if (!row.isConnected) {
        clearInterval(timer);
        done();
        return;
      }
      const progress = Math.min(100, Math.round(Number(row.dataset.progress) + step));
      row.dataset.progress = String(progress);
      if (progress >= 100) {
        clearInterval(timer);
        row.dataset.state = 'done';
      }
      renderRow(row);
      if (progress >= 100) done();
    }, 150);
  }

  /* ---- Note / clip editor autosave ------------------------------------ */

  function initAutosave(form) {
    const status = $('[data-autosave-status]', form);
    let timer;
    form.addEventListener('submit', (event) => event.preventDefault());
    form.addEventListener('input', () => {
      status.textContent = 'Saving…';
      clearTimeout(timer);
      // MOCKUP ONLY: pretend the save took 600ms. S5 posts the form here.
      timer = setTimeout(() => { status.textContent = 'Saved'; }, 600);
    });
  }

  /* ---- Login lockout countdown and Change password -------------------- */

  function waitText(seconds) {
    if (seconds > 90) return `Too many attempts. Try again in ${Math.ceil(seconds / 60)} minutes.`;
    return `Too many attempts. Try again in ${seconds} second${seconds === 1 ? '' : 's'}.`;
  }

  // The server renders the locked form with the button disabled; this counts down and
  // gives the button back when the lock ends.
  function initRetryCountdown(line) {
    const button = $('button[type="submit"]', line.closest('form'));
    const endsAt = Date.now() + Number(line.dataset.retryAfter) * 1000;
    const tick = () => {
      const left = Math.ceil((endsAt - Date.now()) / 1000);
      if (left <= 0) {
        clearInterval(timer);
        line.textContent = '';
        if (button) button.disabled = false;
        return;
      }
      line.textContent = waitText(left);
    };
    const timer = setInterval(tick, 1000);
    tick();
  }

  function initPasswordForm(form) {
    const error = $('[data-password-error]', form);
    const submit = $('button[type="submit"]', form);
    const minLength = Number(form.dataset.minLength);
    const dialog = form.closest('dialog');

    dialog.addEventListener('close', () => {
      form.reset();
      error.textContent = '';
    });

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const { current, new: next, repeat } = form.elements;
      let problem = '';
      if (!current.value) problem = 'Enter your current password.';
      else if (next.value.length < minLength) problem = `The new password needs at least ${minLength} characters.`;
      else if (next.value !== repeat.value) problem = "The new passwords don't match.";
      error.textContent = problem;
      if (problem) return;

      submit.disabled = true;
      try {
        const response = await fetch('/api/password', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ current: current.value, new: next.value }),
        });
        if (response.status === 401) {
          window.location.href = '/login';
          return;
        }
        if (!response.ok) {
          const body = await response.json().catch(() => ({}));
          error.textContent = body.error || "Couldn't change the password. Try again.";
          return;
        }
        dialog.close();
        toast('Password changed');
      } catch {
        error.textContent = "Can't reach the vault. Is Tailscale connected?";
      } finally {
        submit.disabled = false;
      }
    });
  }

  /* ---- Photo viewer --------------------------------------------------- */

  function initViewer(viewer) {
    const track = $('.viewer__track', viewer);
    let idleTimer;

    const showChrome = () => {
      viewer.classList.remove('is-chrome-hidden');
      clearTimeout(idleTimer);
      idleTimer = setTimeout(() => viewer.classList.add('is-chrome-hidden'), 2500);
    };
    const hideChrome = () => {
      clearTimeout(idleTimer);
      viewer.classList.add('is-chrome-hidden');
    };
    const step = (direction) => track.scrollBy({
      left: direction * track.clientWidth,
      behavior: reducedMotion.matches ? 'auto' : 'smooth',
    });

    const start = location.hash && document.getElementById(location.hash.slice(1));
    if (start) track.scrollLeft = start.offsetLeft;

    track.addEventListener('click', () => {
      if (viewer.classList.contains('is-chrome-hidden')) showChrome();
      else hideChrome();
    });
    viewer.addEventListener('pointermove', (event) => {
      if (event.pointerType === 'mouse') showChrome();
    });
    viewer.addEventListener('click', (event) => {
      const button = event.target.closest('[data-viewer-step]');
      if (button) step(Number(button.dataset.viewerStep));
    });
    document.addEventListener('keydown', (event) => {
      if ($('dialog[open]')) return;
      if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
        event.preventDefault();
        step(event.key === 'ArrowRight' ? 1 : -1);
      } else if (event.key === 'Escape') {
        const back = $('[data-viewer-back]');
        if (back) window.location.href = back.href;
      }
    });
    showChrome();
  }

  /* ---- Delegated clicks ----------------------------------------------- */

  const CLICK_TARGETS = [
    '[data-action]', '[data-copy]', '[data-copy-from]', '[data-reveal]', '[data-star]',
    '[data-sheet-open]', '[data-modal-open]', '[data-close]', '[data-toast]', '[data-upload]',
    '[data-upload-cancel]', '[data-upload-retry]', '[data-upload-toggle]',
    '[data-upload-dismiss]', '[data-search-clear]', '.chip',
  ].join(',');

  document.addEventListener('click', (event) => {
    if (event.target instanceof HTMLDialogElement) {
      closeIfBackdrop(event);
      return;
    }
    const target = event.target.closest(CLICK_TARGETS);
    if (!target) return;
    const data = target.dataset;

    if ('action' in data) runAction(target);
    else if ('copy' in data || 'copyFrom' in data) copy(target, copySource(target));
    else if ('reveal' in data) setRevealed(target, target.getAttribute('aria-pressed') !== 'true');
    else if ('star' in data) toggleStar(target);
    else if ('sheetOpen' in data) openSheet(target);
    else if ('modalOpen' in data) document.getElementById(data.modalOpen)?.showModal();
    else if ('close' in data) target.closest('dialog')?.close();
    else if ('toast' in data) toast(data.toast);
    else if ('upload' in data) {
      // S6 replaces this with the real upload.
      if (IS_APP) toast('Uploading is not built yet (stage S6).', { error: true });
      else uploadInput.click();
    }
    else if ('uploadCancel' in data) {
      target.closest('.upload-row').remove();
      updateUploadTitle();
      if (!$('.upload-row')) dismissUploads();
    } else if ('uploadRetry' in data) {
      const row = target.closest('.upload-row');
      Object.assign(row.dataset, { state: 'waiting', progress: '0', error: '' });
      renderRow(row);
      pump();
    } else if ('uploadToggle' in data) {
      const list = $('[data-upload-list]');
      list.hidden = !list.hidden;
      target.setAttribute('aria-expanded', String(!list.hidden));
      target.setAttribute('aria-label', list.hidden ? 'Expand uploads' : 'Collapse uploads');
    } else if ('uploadDismiss' in data) dismissUploads();
    else if ('searchClear' in data) {
      const input = $('input', target.closest('.search-field'));
      input.value = '';
      input.focus();
    } else if (target.classList.contains('chip')) pressChip(target);
  });

  /* "/" focuses search on desktop. */
  document.addEventListener('keydown', (event) => {
    if (event.key !== '/' || event.ctrlKey || event.metaKey || event.altKey) return;
    if (event.target.closest?.('input, textarea, [contenteditable]')) return;
    const field = $$('.search-field__input').find((input) => input.offsetParent !== null);
    if (!field) return;
    event.preventDefault();
    field.focus();
  });

  /* ---- Init ----------------------------------------------------------- */

  $$('[data-autosave]').forEach(initAutosave);
  $$('[data-retry-after]').forEach(initRetryCountdown);
  $$('[data-password-form]').forEach(initPasswordForm);
  $$('.upload-row').forEach(renderRow);
  updateUploadTitle();
  const viewer = $('.viewer');
  if (viewer) initViewer(viewer);
  $$('dialog[data-open-on-load]').forEach((dialog) => dialog.showModal());
})();
