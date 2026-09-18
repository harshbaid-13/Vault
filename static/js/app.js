/* Personal Vault — shared interactions
 *
 * Vanilla JS, no dependencies, no build step. Behaviour hangs off
 * data-attributes through event delegation, so templates never carry
 * inline script and a strict Content-Security-Policy keeps working.
 *
 * Blocks marked MOCKUP ONLY fake a server round-trip for the static
 * mockups; in the app, the same actions call /api.
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

  // The server's MAX_UPLOAD_SIZE_MB, so a file that is too big fails before it is sent.
  const MAX_UPLOAD_BYTES = Number(document.body.dataset.maxUpload) || 2 * 1024 ** 3;
  const MAX_UPLOAD_TEXT = MAX_UPLOAD_BYTES % 1024 ** 3 === 0
    ? `${MAX_UPLOAD_BYTES / 1024 ** 3} GB` : `${Math.round(MAX_UPLOAD_BYTES / 1024 ** 2)} MB`;
  const COPY_FALLBACK_MESSAGE =
    'Press and hold to copy — open the vault over HTTPS for one-tap copy.';
  const OFFLINE_MESSAGE = "Can't reach the vault. Is Tailscale connected?";

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

  /* ---- API calls and refreshing the page ------------------------------ */

  // JSON in, JSON out. Throws an Error whose message is the sentence to show
  // in a toast; error.status is set when the server answered.
  async function api(method, url, body, { keepalive = false } = {}) {
    const options = { method, keepalive, headers: {} };
    if (body !== undefined) {
      options.headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(body);
    }
    let response;
    try {
      response = await fetch(url, options);
    } catch {
      throw new Error(OFFLINE_MESSAGE);
    }
    if (response.ok) return response.status === 204 ? null : response.json();
    const answer = await response.json().catch(() => ({}));
    const error = new Error(answer.error || "That didn't work. Try again.");
    error.status = response.status;
    throw error;
  }

  // After a change, swap in a fresh copy of <main> from the same URL. The
  // server renders it, so no row HTML is ever built here.
  // Ticked rows stay ticked across the swap.
  async function refreshMain() {
    const url = new URL(window.location.href);
    url.searchParams.set('partial', '1');
    const response = await fetch(url);
    if (!response.ok) throw new Error("Saved, but the list didn't refresh. Reload the page.");
    const ticked = new Set($$('[data-select]:checked').map((box) => `${box.dataset.select}:${box.value}`));
    $('main').innerHTML = await response.text();
    $$('[data-select]').forEach((box) => { box.checked = ticked.has(`${box.dataset.select}:${box.value}`); });
    if (selecting) selectionChanged();
  }

  // The folder the Files page shows: a number, or null for the top level (and other pages).
  function currentFolderId() {
    const id = $('[data-folder-id]')?.dataset.folderId;
    return id ? Number(id) : null;
  }

  // "3 folders and 42 files"
  function countText(folders, files) {
    const parts = [];
    if (folders) parts.push(`${folders} folder${folders === 1 ? '' : 's'}`);
    if (files) parts.push(`${files} file${files === 1 ? '' : 's'}`);
    return parts.join(' and ');
  }

  function failed(error) {
    if (error.status === 401) {
      window.location.href = `/login?next=${encodeURIComponent(window.location.pathname)}`;
      return;
    }
    toast(error.message, { error: true });
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

  function setStar(button, on) {
    button.setAttribute('aria-pressed', String(on));
    button.setAttribute('aria-label', `${on ? 'Unfavorite' : 'Favorite'} ${button.dataset.name || ''}`.trim());
  }

  // No toast: the icon changing is the feedback. It flips back if the save fails.
  async function toggleStar(button) {
    const on = button.getAttribute('aria-pressed') !== 'true';
    setStar(button, on);
    if (!button.dataset.item) return;
    try {
      await api('PATCH', button.dataset.item, { favorite: on });
      if ('viewerStar' in button.dataset && viewerSlide) viewerSlide.toggleAttribute('data-favorite', on);
    } catch (error) {
      setStar(button, !on);
      failed(error);
    }
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
    if (trigger.dataset.sheetTitleFrom) {
      trigger.dataset.sheetTitle = $(trigger.dataset.sheetTitleFrom).value.trim() || 'Untitled';
    }
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

  function confirmDelete(title, body = 'This cannot be undone.') {
    const modal = document.getElementById('modal-delete');
    if (!modal) return;
    $('.modal__title', modal).textContent = title;
    $('.modal__body', modal).textContent = body;
    modal.showModal();
  }

  // A folder's confirm says exactly what goes with it.
  async function confirmFolderDelete(trigger, name) {
    try {
      const inside = await api('GET', `${trigger.dataset.item}/summary`);
      const what = countText(inside.folders, inside.files);
      confirmDelete(`Delete ${name}?`, what
        ? `The ${what} inside will be deleted too. This cannot be undone.`
        : 'This cannot be undone.');
    } catch (error) {
      failed(error);
    }
  }

  // A PATCH from a list row's sheet, then the list is re-rendered.
  async function patchAndRefresh(url, fields, message) {
    try {
      await api('PATCH', url, fields);
      await refreshMain();
      toast(message);
    } catch (error) {
      failed(error);
    }
  }

  let deleteTrigger = null;
  let deleteSelection = null;

  async function deleteItem(trigger) {
    try {
      await api('DELETE', trigger.dataset.item);
    } catch (error) {
      // Already gone is what was asked for.
      if (error.status !== 404) {
        failed(error);
        return;
      }
    }
    if ('viewerMenu' in trigger.dataset) {
      viewerRemoveCurrent();
      toast('Deleted');
      return;
    }
    if (trigger.dataset.afterDelete) {
      editorDeleted = true;
      window.location.replace(trigger.dataset.afterDelete);
      return;
    }
    try {
      await refreshMain();
      toast('Deleted');
    } catch (error) {
      failed(error);
    }
  }

  function runAction(item) {
    const dialog = item.closest('dialog');
    const name = sheetTrigger?.dataset.sheetTitle
      || (dialog && $('.sheet__title', dialog)?.textContent)
      || 'this item';
    dialog?.close();
    // Row and editor triggers carry data-item (their /api URL). Without it
    // this is a static mockup and the action is only pretended.
    const trigger = sheetTrigger;
    const url = trigger?.dataset.item;
    const isFavorite = Boolean(trigger && 'favorite' in trigger.dataset);
    const isHidden = Boolean(trigger && 'clipHidden' in trigger.dataset);
    switch (item.dataset.action) {
      case 'toast':
        toast(item.dataset.toast);
        break;
      case 'copy':
        copy(item, copySource(item.dataset.copyFrom ? item : trigger));
        break;
      case 'download':
        // A link with `download` doesn't count as leaving the page, so uploads carry on.
        if (trigger?.dataset.download) {
          const link = el('a');
          link.href = trigger.dataset.download;
          link.download = '';
          document.body.append(link);
          link.click();
          link.remove();
        }
        break;
      case 'rename':
        if (trigger?.dataset.rename !== undefined) openRename(trigger);
        break;
      case 'copy-link':
        // An address inside the vault, not a share link: it only opens for you, logged in.
        writeClipboard(`${window.location.origin}/files/${url.split('/').pop()}`).then((ok) => {
          toast(ok ? 'Link copied. It only works when logged in to your vault.' : COPY_FALLBACK_MESSAGE, { error: !ok });
        });
        break;
      case 'move':
        if (url) openPicker(itemOf(url));
        break;
      case 'new-folder': {
        const modal = document.getElementById('modal-folder');
        modal?.showModal();
        $('input', modal)?.focus();
        break;
      }
      case 'select':
        setSelecting(true);
        break;
      case 'edit':
        if (trigger?.dataset.edit) window.location.href = trigger.dataset.edit;
        break;
      case 'favorite': {
        const message = isFavorite ? 'Removed from Favorites' : 'Added to Favorites';
        if (url) patchAndRefresh(url, { favorite: !isFavorite }, message);
        else toast(message); // MOCKUP ONLY
        break;
      }
      case 'hide': {
        const message = isHidden ? 'Content no longer hidden' : 'Content hidden';
        if (url) patchAndRefresh(url, { hidden: !isHidden }, message);
        else toast(message); // MOCKUP ONLY
        break;
      }
      case 'delete':
        deleteTrigger = trigger;
        deleteSelection = null;
        if (url?.startsWith('/api/folders/')) confirmFolderDelete(trigger, name);
        else confirmDelete(`Delete ${name}?`);
        break;
      case 'confirm-delete':
        if (deleteSelection) deleteSelected(deleteSelection);
        else if (deleteTrigger?.dataset.item) deleteItem(deleteTrigger);
        else toast('Deleted'); // MOCKUP ONLY
        deleteTrigger = null;
        deleteSelection = null;
        break;
      default:
        break;
    }
  }

  /* ---- Filter chips --------------------------------------------------- */

  function pressChip(chip) {
    if (chip.tagName === 'A') return; // a link chip (Favorites, Search) just navigates
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
      Object.assign(row.dataset, { state: 'failed', error: `Too large (max ${MAX_UPLOAD_TEXT})`, final: 'true' });
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

  let autoHideTimer;
  // Two at a time in the app; the mockup's fake upload runs one.
  const PARALLEL_UPLOADS = IS_APP ? 2 : 1;
  const uploadFiles = new WeakMap();
  const uploadRequests = new WeakMap();

  const uploadsActive = () => $$('.upload-row').some((row) => ['waiting', 'uploading'].includes(row.dataset.state));

  function addUploads(files) {
    if (!files.length) return;
    const panel = uploadPanel();
    panel.hidden = false;
    clearTimeout(autoHideTimer);
    const list = $('[data-upload-list]', panel);
    // Uploads go into the folder on screen when they were picked.
    const folderId = currentFolderId();
    files.forEach((file) => {
      const row = uploadRow(file);
      row.dataset.folderId = folderId === null ? '' : String(folderId);
      uploadFiles.set(row, file);
      list.append(row);
    });
    updateUploadTitle();
    pump();
  }

  function pump() {
    const rows = $$('.upload-row');
    let active = rows.filter((row) => row.dataset.state === 'uploading').length;
    rows.filter((row) => row.dataset.state === 'waiting').forEach((row) => {
      if (active >= PARALLEL_UPLOADS) return;
      active += 1;
      row.dataset.state = 'uploading';
      row.dataset.progress = '0';
      renderRow(row);
      (IS_APP ? sendUpload : simulateUpload)(row, () => {
        pump();
        if (!uploadsActive()) uploadsSettled();
      });
    });
    updateUploadTitle();
  }

  // One raw-body request per file (TECH_PLAN §8 gotcha 9). XMLHttpRequest, because fetch
  // can't report upload progress.
  function sendUpload(row, done) {
    const file = uploadFiles.get(row);
    const xhr = new XMLHttpRequest();
    uploadRequests.set(row, xhr);
    const finish = (state, error = '', final = false) => {
      Object.assign(row.dataset, { state, error, final: String(final) });
      renderRow(row);
      done();
    };
    xhr.open('POST', row.dataset.folderId ? `/api/files?folder_id=${row.dataset.folderId}` : '/api/files');
    xhr.setRequestHeader('Content-Type', 'application/octet-stream');
    xhr.setRequestHeader('X-File-Name', encodeURIComponent(file.name));
    xhr.upload.addEventListener('progress', (event) => {
      if (!event.lengthComputable || row.dataset.state !== 'uploading') return;
      row.dataset.progress = String(Math.floor((event.loaded / event.total) * 100));
      renderRow(row);
    });
    xhr.addEventListener('load', () => {
      if (xhr.status === 201) {
        finish('done');
        refreshAfterUpload();
        return;
      }
      let message = '';
      try {
        message = JSON.parse(xhr.responseText).error;
      } catch {
        /* not JSON */
      }
      if (xhr.status === 401) message = 'Logged out. Reload the page to log in.';
      finish('failed', message || "Couldn't upload. Try again.", xhr.status === 413);
    });
    xhr.addEventListener('error', () => finish('failed', 'Connection lost'));
    xhr.addEventListener('abort', () => done());
    xhr.send(file);
  }

  // The Files list re-renders from the server after each upload, a moment later so a batch
  // of small files refreshes once.
  let refreshTimer;
  function refreshAfterUpload() {
    if (!$('[data-refresh-after-upload]')) return;
    clearTimeout(refreshTimer);
    refreshTimer = setTimeout(() => refreshMain().catch(failed), 300);
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

  // Pages are real page loads, so leaving cancels uploads: ask first (TECH_PLAN gotcha 13).
  window.addEventListener('beforeunload', (event) => {
    if (!uploadsActive()) return;
    event.preventDefault();
    event.returnValue = '';
  });

  /* ---- Drag and drop (desktop) ---------------------------------------- */

  let dragDepth = 0;
  const dropOverlay = el('div', 'drop-overlay');
  dropOverlay.hidden = true;
  dropOverlay.append(icon('upload', 'icon--lg'), el('p', 'drop-overlay__text', 'Drop to upload'));
  if (IS_APP && $('.tabbar, .sidebar')) document.body.append(dropOverlay);

  const draggingFiles = (event) => Array.from(event.dataTransfer?.types || []).includes('Files');

  document.addEventListener('dragenter', (event) => {
    if (!dropOverlay.isConnected || !draggingFiles(event)) return;
    event.preventDefault();
    dragDepth += 1;
    dropOverlay.hidden = false;
  });
  document.addEventListener('dragover', (event) => {
    if (dropOverlay.isConnected && draggingFiles(event)) event.preventDefault();
  });
  document.addEventListener('dragleave', (event) => {
    if (!dropOverlay.isConnected || !draggingFiles(event)) return;
    dragDepth = Math.max(0, dragDepth - 1);
    if (!dragDepth) dropOverlay.hidden = true;
  });
  document.addEventListener('drop', (event) => {
    if (!dropOverlay.isConnected || !draggingFiles(event)) return;
    event.preventDefault();
    dragDepth = 0;
    dropOverlay.hidden = true;
    // A dropped folder shows up as a File with no type and can't be read; skip those.
    const items = Array.from(event.dataTransfer.items || []);
    addUploads(Array.from(event.dataTransfer.files)
      .filter((file, index) => !items[index]?.webkitGetAsEntry?.()?.isDirectory));
  });

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

  let editorDeleted = false;

  // Saves 800ms after typing stops, when the page is hidden (phone locked,
  // app switched) and when it is left. Leaving with no title and no text
  // deletes the item, so a stray ＋ New leaves nothing behind.
  function initEditor(form) {
    const url = form.dataset.editor;
    const status = $('[data-autosave-status]', form);
    const fields = $$('input[type="text"], textarea', form);
    const hiddenSwitch = $('[data-editor-hidden]', form);
    let timer;
    let dirty = false;
    let inFlight = false;
    let failing = false;

    const values = () => Object.fromEntries(fields.map((field) => [field.name, field.value]));
    const isEmpty = () => fields.every((field) => !field.value.trim());
    const clock = () => new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });

    async function save({ keepalive = false } = {}) {
      clearTimeout(timer);
      if (!dirty || editorDeleted) return;
      if (inFlight && !keepalive) {
        timer = setTimeout(save, 300);
        return;
      }
      dirty = false;
      inFlight = true;
      status.textContent = 'Saving…';
      try {
        await api('PATCH', url, values(), { keepalive });
        failing = false;
        if (!dirty) status.textContent = `Saved · Today, ${clock()}`;
      } catch (error) {
        dirty = true;
        status.textContent = 'Not saved — retrying… Your text is still here.';
        // One toast, then keep retrying quietly.
        if (!failing) toast(error.status === 401 ? 'You were logged out. Copy your text, then reload to log in.' : error.message, { error: true });
        failing = true;
        if (error.status !== 401 && error.status !== 404 && error.status !== 422) timer = setTimeout(save, 5000);
      } finally {
        inFlight = false;
      }
    }

    form.addEventListener('submit', (event) => event.preventDefault());
    form.addEventListener('input', (event) => {
      if (event.target === hiddenSwitch) return;
      dirty = true;
      clearTimeout(timer);
      timer = setTimeout(save, 800);
    });

    // Autosave already does the work; Save is there so finishing feels deliberate.
    const saveButton = $('[data-editor-save]');
    let savedTimer;
    saveButton?.addEventListener('click', async () => {
      if (isEmpty()) {
        toast('Type something first.');
        return;
      }
      clearTimeout(timer);
      while (inFlight) await new Promise((resolve) => { setTimeout(resolve, 100); });
      const wasFailing = failing;
      await save();
      if (dirty) {
        if (wasFailing) toast('Not saved yet — still retrying.', { error: true });
        return;
      }
      toast('Saved');
      saveButton.textContent = 'Saved ✓';
      clearTimeout(savedTimer);
      savedTimer = setTimeout(() => { saveButton.textContent = 'Save'; }, 1500);
    });

    hiddenSwitch?.addEventListener('change', async () => {
      const on = hiddenSwitch.checked;
      try {
        await api('PATCH', url, { hidden: on });
      } catch (error) {
        hiddenSwitch.checked = !on;
        failed(error);
      }
    });

    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') save({ keepalive: true });
    });

    window.addEventListener('pagehide', () => {
      if (editorDeleted) return;
      if (isEmpty()) {
        editorDeleted = true;
        // sendBeacon can't send DELETE.
        fetch(url, { method: 'DELETE', keepalive: true }).catch(() => {});
      } else {
        save({ keepalive: true });
      }
    });

    // Links out of the editor wait for the last save (or the discard), so the
    // page they open never shows stale text. pagehide above covers the rest.
    document.addEventListener('click', async (event) => {
      const link = event.target.closest('a[href]');
      if (!link || event.defaultPrevented || event.button !== 0
        || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      if (!isEmpty() && !dirty) return;
      event.preventDefault();
      if (isEmpty()) {
        editorDeleted = true;
        await api('DELETE', url).catch(() => {});
      } else {
        await save({ keepalive: true });
      }
      window.location.href = link.href;
    });

    // Coming back to a discarded item from history: it no longer exists.
    window.addEventListener('pageshow', (event) => {
      if (event.persisted && editorDeleted) window.location.replace(form.dataset.back);
    });

    if (isEmpty()) $(form.dataset.focus || 'input', form)?.focus();
  }

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

  /* ---- Rename (files) ------------------------------------------------ */

  let renameTrigger = null;

  function openRename(trigger) {
    const modal = document.getElementById('modal-rename');
    if (!modal) return;
    renameTrigger = trigger;
    const input = $('input', modal);
    input.value = trigger.dataset.rename;
    $('[data-rename-error]', modal).textContent = '';
    modal.showModal();
    input.focus();
    // Select a file's name but not its extension, like a file manager. A folder has none.
    const dot = trigger.dataset.item.startsWith('/api/folders/') ? -1 : input.value.lastIndexOf('.');
    input.setSelectionRange(0, dot > 0 ? dot : input.value.length);
  }

  function initRenameForm(form) {
    const error = $('[data-rename-error]', form);
    const submit = $('button[type="submit"]', form);
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const name = form.elements.name.value;
      if (!name.trim()) {
        error.textContent = 'Enter a name.';
        return;
      }
      submit.disabled = true;
      try {
        const renamed = await api('PATCH', renameTrigger.dataset.item, { name });
        form.closest('dialog').close();
        // Header buttons live outside <main>, so they learn the new name here.
        Object.assign(renameTrigger.dataset, { rename: renamed.name, sheetTitle: renamed.name });
        if (renameTrigger.dataset.copy !== undefined) renameTrigger.dataset.copy = renamed.name;
        if (viewerSlide) {
          viewerSlide.dataset.name = renamed.name;
          $('[data-caption-name]', viewerSlide).textContent = renamed.name;
          const img = $('img', viewerSlide);
          if (img) img.alt = renamed.name;
          document.title = `${renamed.name} · My Vault`;
        } else {
          await refreshMain();
        }
        toast('Renamed');
      } catch (problem) {
        if (problem.status === 401) failed(problem);
        else error.textContent = problem.message;
      } finally {
        submit.disabled = false;
      }
    });
  }

  function initFolderForm(form) {
    const error = $('[data-folder-error]', form);
    const submit = $('button[type="submit"]', form);
    const dialog = form.closest('dialog');
    dialog.addEventListener('close', () => {
      form.reset();
      error.textContent = '';
    });
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const name = form.elements.name.value;
      if (!name.trim()) {
        error.textContent = 'Enter a name.';
        return;
      }
      submit.disabled = true;
      try {
        await api('POST', '/api/folders', { name, parent_id: currentFolderId() });
        dialog.close();
        await refreshMain();
        toast('Folder created');
      } catch (problem) {
        if (problem.status === 401) failed(problem);
        else error.textContent = problem.message;
      } finally {
        submit.disabled = false;
      }
    });
  }

  /* ---- Files: select mode --------------------------------------------- */
  /* Header ⋯ → Select on a phone; on a desktop the checkboxes are always there
     and ticking one starts it. Unticking the last one ends it. */

  let selecting = false;
  let lastTicked = null;

  function selection() {
    const boxes = $$('[data-select]:checked');
    return {
      files: boxes.filter((box) => box.dataset.select === 'files').map((box) => box.value),
      folders: boxes.filter((box) => box.dataset.select === 'folders').map((box) => Number(box.value)),
    };
  }

  function setSelecting(on) {
    const head = $('[data-select-head]');
    if (!head) return;
    selecting = on;
    document.body.classList.toggle('is-selecting', on);
    head.hidden = !on;
    $('[data-select-bar]').hidden = !on;
    if (!on) {
      $$('[data-select]').forEach((box) => { box.checked = false; });
      lastTicked = null;
    }
    selectionChanged();
  }

  function selectionChanged() {
    const boxes = $$('[data-select]');
    const count = boxes.filter((box) => box.checked).length;
    if (count && !selecting) {
      setSelecting(true);
      return;
    }
    if (!selecting) return;
    $('[data-select-count]').textContent = `${count} selected`;
    $('[data-select-move]').disabled = !count;
    $('[data-select-delete]').disabled = !count;
    const visible = boxes.filter((box) => !box.closest('.row').hidden);
    $('[data-select-all]').textContent = visible.length && visible.every((box) => box.checked) ? 'Select none' : 'Select all';
  }

  // Shift-click ticks (or unticks) every row between the last one and this one.
  function tick(box, range) {
    if (range && lastTicked?.isConnected) {
      const boxes = $$('[data-select]').filter((other) => !other.closest('.row').hidden);
      const [from, to] = [boxes.indexOf(lastTicked), boxes.indexOf(box)].sort((a, b) => a - b);
      if (from >= 0) boxes.slice(from, to + 1).forEach((other) => { other.checked = box.checked; });
    }
    lastTicked = box;
    selectionChanged();
  }

  function selectAll() {
    const visible = $$('[data-select]').filter((box) => !box.closest('.row').hidden);
    const on = !visible.every((box) => box.checked);
    visible.forEach((box) => { box.checked = on; });
    selectionChanged();
  }

  function deleteSelectedAsk() {
    const items = selection();
    const folderIds = items.folders;
    if (!folderIds.length) {
      deleteSelection = items;
      confirmDelete(`Delete ${countText(0, items.files.length)}?`);
      return;
    }
    // Count what is inside the folders too, so the confirm names everything that goes.
    Promise.all(folderIds.map((id) => api('GET', `/api/folders/${id}/summary`)))
      .then((inside) => {
        const folders = folderIds.length + inside.reduce((sum, one) => sum + one.folders, 0);
        const files = items.files.length + inside.reduce((sum, one) => sum + one.files, 0);
        deleteSelection = items;
        deleteTrigger = null;
        confirmDelete(`Delete ${countText(folders, files)}?`);
      })
      .catch(failed);
  }

  async function deleteSelected(items) {
    try {
      await api('POST', '/api/delete', items);
      setSelecting(false);
      await refreshMain();
      toast('Deleted');
    } catch (error) {
      failed(error);
    }
  }

  // In select mode a tap on a row ticks it instead of opening it.
  document.addEventListener('click', (event) => {
    const box = event.target.closest?.('[data-select]');
    if (box) {
      tick(box, event.shiftKey);
      return;
    }
    if (!selecting) return;
    const link = event.target.closest?.('.row__link');
    const rowBox = link && $('[data-select]', link.closest('.row'));
    if (!rowBox) return;
    event.preventDefault();
    rowBox.checked = !rowBox.checked;
    tick(rowBox, event.shiftKey);
  });

  /* ---- Files: move picker --------------------------------------------- */
  /* Opens in the folder being shown. The folders being moved aren't listed, so
     nothing can be moved into itself (the server checks too). */

  const picker = { tree: [], at: null, from: null, items: null };

  // "/api/files/<id>" → {files: [id], folders: []}
  function itemOf(url) {
    const [, kind, id] = url.match(/^\/api\/(files|folders)\/(.+)$/);
    return kind === 'files' ? { files: [id], folders: [] } : { files: [], folders: [Number(id)] };
  }

  async function openPicker(items) {
    const dialog = document.getElementById('sheet-move');
    if (!dialog) return;
    try {
      picker.tree = (await api('GET', '/api/folders')).folders;
    } catch (error) {
      failed(error);
      return;
    }
    Object.assign(picker, { items, from: currentFolderId(), at: currentFolderId() });
    $('[data-picker-what]', dialog).textContent = `Move ${countText(items.folders.length, items.files.length)} to…`;
    renderPicker();
    dialog.showModal();
  }

  function renderPicker() {
    const dialog = document.getElementById('sheet-move');
    const here = picker.tree.find((folder) => folder.id === picker.at);
    if (!here) picker.at = null;
    const moving = new Set(picker.items.folders);
    const inside = picker.tree.filter((folder) => folder.parent_id === picker.at && !moving.has(folder.id));
    $('[data-picker-title]', dialog).textContent = here ? here.name : 'Files';
    $('[data-picker-up]', dialog).disabled = picker.at === null;
    $('[data-picker-list]', dialog).replaceChildren(...inside.map((folder) => {
      const button = el('button', 'sheet__item');
      button.type = 'button';
      button.dataset.pickerOpen = String(folder.id);
      button.append(icon('folder', 'icon--sm'), el('span', 'picker__name', folder.name), icon('chevron-right', 'icon--sm picker__chevron'));
      const item = el('li');
      item.append(button);
      return item;
    }));
    $('[data-picker-empty]', dialog).hidden = inside.length > 0;
    // Everything being moved sits in the folder this page shows.
    $('[data-picker-confirm]', dialog).disabled = picker.at === picker.from;
  }

  function pickerGo(folderId) {
    picker.at = folderId;
    renderPicker();
    $('[data-picker-up]').focus();
  }

  async function moveHere(button) {
    const dialog = button.closest('dialog');
    const { items, at } = picker;
    const destination = picker.tree.find((folder) => folder.id === at)?.name || 'Files';
    button.disabled = true;
    try {
      await api('POST', '/api/move', { ...items, to: at });
      dialog.close();
      setSelecting(false);
      await refreshMain();
      const count = items.files.length + items.folders.length;
      toast(count === 1 ? `Moved to ${destination}` : `Moved ${countText(items.folders.length, items.files.length)} to ${destination}`);
    } catch (error) {
      // A toast can't show above an open dialog.
      dialog.close();
      failed(error);
    } finally {
      button.disabled = false;
    }
  }

  /* ---- Live search ----------------------------------------------------- */
  /* Results refresh 250 ms after typing stops, from 2 characters. The address follows the
     field, so Back, refresh and Enter all land on the same results. */

  function initLiveSearch(form) {
    const input = form.elements.q;
    const type = form.elements.type;
    let timer;
    let latest = 0;

    async function run() {
      const q = input.value.trim();
      if (q.length === 1) return;
      const url = new URL('/search', window.location.origin);
      if (q) url.searchParams.set('q', q);
      url.searchParams.set('type', type.value);
      history.replaceState(history.state, '', url);
      url.searchParams.set('partial', '1');
      const ticket = ++latest;
      try {
        const response = await fetch(url);
        if (response.status === 401) {
          failed({ status: 401 });
          return;
        }
        if (!response.ok) throw new Error("Search didn't work. Try again.");
        const html = await response.text();
        if (ticket === latest) $('main').innerHTML = html; // an older, slower answer never wins
      } catch (error) {
        failed(error.message ? error : new Error(OFFLINE_MESSAGE));
      }
    }

    input.addEventListener('input', () => {
      clearTimeout(timer);
      timer = setTimeout(run, 250);
    });
    // Put the cursor at the end of a query already there.
    if (input.value) input.setSelectionRange(input.value.length, input.value.length);
  }

  /* ---- Files: filter box ---------------------------------------------- */

  document.addEventListener('input', (event) => {
    const input = event.target.closest?.('[data-filter]');
    if (!input) return;
    const term = input.value.trim().toLocaleLowerCase();
    let shown = 0;
    $$('[data-select-list] > [data-name]').forEach((row) => {
      const match = !term || row.dataset.name.toLocaleLowerCase().includes(term);
      row.hidden = !match;
      if (match) shown += 1;
    });
    const empty = $('[data-filter-empty]');
    if (empty) empty.hidden = shown > 0;
    if (selecting) selectionChanged();
  });

  document.addEventListener('submit', (event) => {
    if (event.target.matches('[data-filter-form]')) event.preventDefault();
  });

  /* ---- Link form ----------------------------------------------------- */

  function initLinkForm(form) {
    const error = $('[data-link-error]', form);
    const submit = $('button[type="submit"]', form);
    // Typing http:// or https:// yourself moves the switch to match.
    const { url: address, use_http: httpSwitch } = form.elements;
    address.addEventListener('input', () => {
      if (/^http:\/\//i.test(address.value.trim())) httpSwitch.checked = true;
      else if (/^https:\/\//i.test(address.value.trim())) httpSwitch.checked = false;
    });
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const { url, title, description, use_http: useHttp } = form.elements;
      if (!url.value.trim()) {
        error.textContent = "Enter the link's address.";
        url.focus();
        return;
      }
      error.textContent = '';
      submit.disabled = true;
      try {
        await api(form.dataset.method, form.dataset.linkForm, {
          url: url.value, title: title.value, description: description.value, use_http: useHttp.checked,
        });
        window.location.href = '/links';
      } catch (problem) {
        if (problem.status === 401) failed(problem);
        else error.textContent = problem.message;
        submit.disabled = false;
      }
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

  /* ---- Settings: connection checks ----------------------------------- */
  /* The server sees plain http behind tailscale serve, so only the page can tell. */

  function runConnectionChecks() {
    const results = {
      https: window.location.protocol === 'https:',
      clipboard: window.isSecureContext && Boolean(navigator.clipboard),
    };
    let allOk = true;
    $$('[data-check]').forEach((cell) => {
      const ok = results[cell.dataset.check];
      allOk = allOk && ok;
      cell.textContent = ok ? 'Yes ✓' : 'No';
      cell.classList.add(ok ? 'kv__value--ok' : 'kv__value--bad');
    });
    const help = $('[data-check-help]');
    if (help) help.hidden = allOk;
  }

  /* ---- Photo viewer --------------------------------------------------- */
  /* Slides are a scroll-snap strip, so swiping is the browser's own. This keeps the
     header star, the ⋯ sheet and the address in step with the slide on screen. */

  let viewerSlide = null;
  let viewerRemoveCurrent = null;

  function initViewer(viewer) {
    const track = $('.viewer__track', viewer);
    let idleTimer;
    let settleTimer;

    const showChrome = () => {
      viewer.classList.remove('is-chrome-hidden');
      clearTimeout(idleTimer);
      idleTimer = setTimeout(() => viewer.classList.add('is-chrome-hidden'), 2500);
    };
    const hideChrome = () => {
      clearTimeout(idleTimer);
      viewer.classList.add('is-chrome-hidden');
    };
    const slides = () => $$('.viewer__slide', track);
    const step = (direction) => track.scrollBy({
      left: direction * track.clientWidth,
      behavior: reducedMotion.matches ? 'auto' : 'smooth',
    });

    function show(slide) {
      viewerSlide = slide;
      const { id, name } = slide.dataset;
      const star = $('[data-viewer-star]');
      star.dataset.item = `/api/files/${id}`;
      setStar(star, 'favorite' in slide.dataset);
      Object.assign($('[data-viewer-menu]').dataset, {
        item: `/api/files/${id}`, sheetTitle: name, download: `/api/files/${id}/download`, rename: name,
      });
      document.title = `${name} · My Vault`;
      history.replaceState(history.state, '', `/photos/${id}`);
      $$('video', track).forEach((video) => { if (!slide.contains(video)) video.pause(); });
      // Past the neighbours this page was sent with: reload around this one.
      const all = slides();
      if ((slide === all[0] && 'moreNewer' in track.dataset)
        || (slide === all[all.length - 1] && 'moreOlder' in track.dataset)) {
        window.location.replace(`/photos/${id}`);
      }
    }

    function settle() {
      const all = slides();
      const slide = all[Math.round(track.scrollLeft / track.clientWidth)];
      if (slide && slide !== viewerSlide) show(slide);
    }

    // Back, ✕ and Escape return to the grid the way the browser's Back does, keeping its scroll.
    function close() {
      const cameFromPhotos = document.referrer.startsWith(`${window.location.origin}/photos`);
      if (cameFromPhotos && history.length > 1) history.back();
      else window.location.href = '/photos';
    }

    viewerRemoveCurrent = () => {
      const all = slides();
      const index = all.indexOf(viewerSlide);
      viewerSlide.remove();
      const next = all[index + 1] || all[index - 1];
      if (!next) {
        window.location.replace('/photos');
        return;
      }
      track.scrollLeft = next.offsetLeft;
      show(next);
    };

    const start = $('[data-current]', track) || slides()[0];
    track.scrollLeft = start.offsetLeft;
    show(start);

    track.addEventListener('scroll', () => {
      clearTimeout(settleTimer);
      settleTimer = setTimeout(settle, 120);
    });
    window.addEventListener('resize', () => { track.scrollLeft = viewerSlide.offsetLeft; });
    track.addEventListener('click', (event) => {
      if (event.target.closest('video, a, button')) return;
      if (viewer.classList.contains('is-chrome-hidden')) showChrome();
      else hideChrome();
    });
    viewer.addEventListener('pointermove', (event) => {
      if (event.pointerType === 'mouse') showChrome();
    });
    viewer.addEventListener('click', (event) => {
      const button = event.target.closest('[data-viewer-step]');
      if (button) step(Number(button.dataset.viewerStep));
      const back = event.target.closest('[data-viewer-back]');
      if (back && event.button === 0 && !event.ctrlKey && !event.metaKey) {
        event.preventDefault();
        close();
      }
    });
    document.addEventListener('keydown', (event) => {
      if ($('dialog[open]')) return;
      if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
        event.preventDefault();
        step(event.key === 'ArrowRight' ? 1 : -1);
      } else if (event.key === 'Escape') {
        close();
      }
    });
    showChrome();
  }

  /* ---- Photos grid: load the next 60 as the end comes into view ------- */

  function initPhotos(container) {
    let loading = false;
    const observer = 'IntersectionObserver' in window
      ? new IntersectionObserver((entries) => {
        if (entries.some((entry) => entry.isIntersecting)) loadMore();
      }, { rootMargin: '800px' })
      : null;

    async function loadMore() {
      const link = $('[data-photos-more]', container);
      if (!link || loading) return;
      loading = true;
      try {
        const url = new URL(link.href);
        url.searchParams.set('partial', '1');
        const response = await fetch(url);
        if (response.status === 401) {
          failed({ status: 401 });
          return;
        }
        if (!response.ok) throw new Error("Couldn't load more photos. Scroll to try again.");
        // The server rendered these tiles; they're parsed here, never built.
        const page = document.createElement('template');
        page.innerHTML = await response.text();
        link.remove();
        $$('.photo-month', page.content).forEach((section) => {
          const last = $$('.photo-month', container).pop();
          if (last && last.dataset.month === section.dataset.month) {
            $('.photo-grid', last).append(...$('.photo-grid', section).children);
          } else {
            container.append(section);
          }
        });
        const next = $('[data-photos-more]', page.content);
        if (next) {
          container.append(next);
          observer?.observe(next);
        }
      } catch (error) {
        failed(error);
      } finally {
        loading = false;
      }
    }

    container.addEventListener('click', (event) => {
      if (!event.target.closest('[data-photos-more]')) return;
      event.preventDefault();
      loadMore();
    });
    const link = $('[data-photos-more]', container);
    if (link) observer?.observe(link);
  }

  // A thumbnail that can't exist (HEIC, corrupt) 404s: hide the <img> and the icon under it shows.
  document.addEventListener('error', (event) => {
    if (event.target instanceof HTMLImageElement && 'thumb' in event.target.dataset) event.target.hidden = true;
  }, true);

  /* ---- Delegated clicks ----------------------------------------------- */

  const CLICK_TARGETS = [
    '[data-action]', '[data-copy]', '[data-copy-from]', '[data-reveal]', '[data-star]',
    '[data-sheet-open]', '[data-modal-open]', '[data-close]', '[data-toast]', '[data-upload]',
    '[data-upload-cancel]', '[data-upload-retry]', '[data-upload-toggle]',
    '[data-upload-dismiss]', '[data-search-clear]', '.chip', '[data-select-cancel]', '[data-select-all]',
    '[data-select-move]', '[data-select-delete]', '[data-picker-open]', '[data-picker-up]', '[data-picker-confirm]',
  ].join(',');

  document.addEventListener('click', (event) => {
    if (event.target instanceof HTMLDialogElement) {
      closeIfBackdrop(event);
      return;
    }
    const target = event.target.closest(CLICK_TARGETS);
    if (!target) return;
    const data = target.dataset;

    // A ⋯ button can carry data-copy for its sheet's Copy action, so the sheet check comes first.
    if ('action' in data) runAction(target);
    else if ('sheetOpen' in data) openSheet(target);
    else if ('copy' in data || 'copyFrom' in data) copy(target, copySource(target));
    else if ('reveal' in data) setRevealed(target, target.getAttribute('aria-pressed') !== 'true');
    else if ('star' in data) toggleStar(target);
    else if ('modalOpen' in data) document.getElementById(data.modalOpen)?.showModal();
    else if ('close' in data) target.closest('dialog')?.close();
    else if ('toast' in data) toast(data.toast);
    else if ('upload' in data) uploadInput.click();
    else if ('uploadCancel' in data) {
      const row = target.closest('.upload-row');
      row.remove();
      uploadRequests.get(row)?.abort();
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
      input.dispatchEvent(new Event('input', { bubbles: true }));
    } else if (target.classList.contains('chip')) pressChip(target);
    else if ('selectCancel' in data) setSelecting(false);
    else if ('selectAll' in data) selectAll();
    else if ('selectMove' in data) openPicker(selection());
    else if ('selectDelete' in data) deleteSelectedAsk();
    else if ('pickerOpen' in data) pickerGo(Number(data.pickerOpen));
    else if ('pickerUp' in data) pickerGo(picker.tree.find((folder) => folder.id === picker.at)?.parent_id ?? null);
    else if ('pickerConfirm' in data) moveHere(target);
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && selecting && !$('dialog[open]')) setSelecting(false);
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
  $$('[data-editor]').forEach(initEditor);
  $$('[data-link-form]').forEach(initLinkForm);
  $$('[data-rename-form]').forEach(initRenameForm);
  $$('[data-folder-form]').forEach(initFolderForm);
  $$('[data-live-search]').forEach(initLiveSearch);
  $$('[data-retry-after]').forEach(initRetryCountdown);
  $$('[data-password-form]').forEach(initPasswordForm);
  if ($('[data-check]')) runConnectionChecks();
  $$('.upload-row').forEach(renderRow);
  updateUploadTitle();
  $$('img[data-thumb]').forEach((img) => { if (img.complete && !img.naturalWidth) img.hidden = true; });
  const viewer = $('.viewer');
  if (viewer) initViewer(viewer);
  const photos = $('[data-photos]');
  if (photos) initPhotos(photos);
  // The PDF preview is framed only where it's shown (desktop); a phone gets Open PDF instead.
  $$('[data-pdf-src]').forEach((frame) => { if (pointerFine.matches) frame.src = frame.dataset.pdfSrc; });
  $$('dialog[data-open-on-load]').forEach((dialog) => dialog.showModal());
})();
