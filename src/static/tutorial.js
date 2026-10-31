(() => {
  const dialog = document.querySelector('#tutorial-dialog');
  if (!dialog) return;

  const preferenceKey = 'smergers.tutorial.dismissed.v1';
  const role = dialog.dataset.tutorialRole;
  const steps = [
    {
      icon: '⌂', kicker: 'Welcome to your workspace', title: 'Keep every event change in view',
      description: 'SMErgers connects an event’s quote, WhatsApp decisions, approvals and draft billing in one traceable project record.',
      note: 'Use the workspace tabs to move between the overview, projects and the items that need attention.'
    },
    {
      icon: '⇧', kicker: '1 · Bring in the agreement', title: 'Start with a project and its source',
      description: 'For an existing event, import its WhatsApp text export and choose the matching quote. You can also add a project with quote lines and a chat, or connect a group for ongoing sync.',
      note: 'Imports accept a WhatsApp .txt export without media. The optional AI reader can fall back to the rules reader.'
    },
    {
      icon: '⌕', kicker: '2 · Review the evidence', title: 'Check suggested changes against the chat',
      description: 'Open a project to compare each suggested change with its linked source messages. Check the highlighted evidence, adjust details or price, and add a missed change when needed.',
      note: 'Suggestions are candidates for a person to review. A highlighted message is evidence to inspect, not automatic approval.'
    },
    {
      icon: '✓', kicker: '3 · Move decisions forward', title: 'Review, approve and confirm',
      description: 'The project manager checks changes first. Items that need director sign-off go to the decision queue. The client can then confirm a change or explain a dispute.',
      note: role === 'owner' ? 'As project director, focus on exceptions awaiting your sign-off.' : role === 'client' ? 'As a client, choose the event and respond to each change on its confirmation page.' : 'Your queue and checklist show the next actions for the selected demo role.'
    },
    {
      icon: '▤', kicker: '4 · Reconcile the outcome', title: 'Use confirmed changes for draft billing',
      description: 'Finance can review reconciled totals on each project, open a draft bill and export a CSV for accounting review. The activity log keeps a record of decisions.',
      note: 'Draft bills are for review; this prototype does not send invoices or take payment. Use the Workflow guide in the sidebar for more detail.'
    }
  ];
  const heading = dialog.querySelector('[data-tutorial-heading]');
  const kicker = dialog.querySelector('[data-tutorial-kicker]');
  const icon = dialog.querySelector('[data-tutorial-icon]');
  const description = dialog.querySelector('[data-tutorial-description]');
  const note = dialog.querySelector('[data-tutorial-note]');
  const count = dialog.querySelector('[data-tutorial-count]');
  const progress = dialog.querySelector('[data-tutorial-progress-bar]');
  const back = dialog.querySelector('[data-tutorial-back]');
  const next = dialog.querySelector('[data-tutorial-next]');
  const done = dialog.querySelector('[data-tutorial-done]');
  let current = 0;
  let opener = null;

  function wasDismissed() {
    try { return localStorage.getItem(preferenceKey) === 'yes'; }
    catch { return false; }
  }

  function rememberDismissal() {
    try { localStorage.setItem(preferenceKey, 'yes'); }
    catch { /* The dialog remains usable when storage is unavailable. */ }
  }

  function renderStep() {
    const step = steps[current];
    kicker.textContent = step.kicker;
    heading.textContent = step.title;
    icon.textContent = step.icon;
    description.textContent = step.description;
    note.textContent = step.note;
    count.textContent = `Step ${current + 1} of ${steps.length}`;
    progress.style.width = `${((current + 1) / steps.length) * 100}%`;
    dialog.querySelector('.tutorial-progress').setAttribute('aria-valuenow', String(current + 1));
    dialog.querySelector('.tutorial-progress').setAttribute('aria-valuemax', String(steps.length));
    back.disabled = current === 0;
    next.hidden = current === steps.length - 1;
    done.hidden = current !== steps.length - 1;
  }

  function openTutorial(trigger) {
    opener = trigger || document.activeElement;
    current = 0;
    renderStep();
    if (!dialog.open) dialog.showModal();
  }

  function closeTutorial() {
    rememberDismissal();
    if (dialog.open) dialog.close();
  }

  dialog.querySelectorAll('[data-tutorial-close]').forEach(button => button.addEventListener('click', closeTutorial));
  document.querySelectorAll('[data-tutorial-open]').forEach(button => button.addEventListener('click', () => openTutorial(button)));
  back.addEventListener('click', () => { if (current > 0) { current -= 1; renderStep(); } });
  next.addEventListener('click', () => { if (current < steps.length - 1) { current += 1; renderStep(); } });
  done.addEventListener('click', closeTutorial);
  dialog.addEventListener('cancel', rememberDismissal);
  dialog.addEventListener('click', event => {
    if (event.target === dialog) closeTutorial();
  });
  dialog.addEventListener('close', () => {
    rememberDismissal();
    if (opener && opener.isConnected) opener.focus();
  });
  dialog.addEventListener('keydown', event => {
    if (event.altKey || event.ctrlKey || event.metaKey || event.target.matches('input, textarea, select')) return;
    if (event.key === 'ArrowRight' && current < steps.length - 1) {
      event.preventDefault(); current += 1; renderStep();
    } else if (event.key === 'ArrowLeft' && current > 0) {
      event.preventDefault(); current -= 1; renderStep();
    }
  });

  if (!wasDismissed()) openTutorial(null);
})();
