(() => {
  const dialog = document.querySelector('#tutorial-dialog');
  if (!dialog) return;

  const preferenceKey = 'smergers.tutorial.dismissed.v1';
  const role = dialog.dataset.tutorialRole;
  const spotlight = dialog.querySelector('.tutorial-spotlight');
  const card = dialog.querySelector('.tutorial-sheet');
  const steps = [
    {
      kicker: 'Welcome to your workspace', title: 'Start from Overview',
      description: 'Choose Overview to see project status, changes that need attention and your role checklist.',
      note: 'Follow the highlighted area to find your starting point.'
    },
    {
      kicker: '1 · Bring in the agreement', title: 'Bring a conversation into the project',
      description: 'Import a WhatsApp text export and match it to the quote for the same event. You can also add a project or connect a group for ongoing sync.',
      note: 'Export without media. The optional AI reader can fall back to the rules reader.'
    },
    {
      kicker: '2 · Check the source', title: 'Open the project and review its evidence',
      description: 'Compare each suggested change with the linked WhatsApp messages. Check the highlighted source, update price or details, and add a missed change when needed.',
      note: 'Suggestions need a person to review them; a highlighted message is evidence, not automatic approval.'
    },
    {
      kicker: '3 · Move the decision forward', title: 'Choose the next action for your role',
      description: 'Project managers check changes first. Directors review exceptions. Clients confirm a change or explain a dispute.',
      note: role === 'owner' ? 'Open your decision queue to see items waiting for sign-off.' : role === 'client' ? 'Choose an event, then respond to its changes.' : 'Your queue and checklist point to the actions waiting for you.'
    },
    {
      kicker: '4 · Reconcile the outcome', title: 'Finish with a record or draft bill',
      description: 'Finance reviews totals made from client-confirmed changes and can export a CSV for accounting. The workflow guide explains each stage in more detail.',
      note: 'Draft bills are for review; this prototype does not send invoices or take payment.'
    }
  ];
  const heading = dialog.querySelector('[data-tutorial-heading]');
  const kicker = dialog.querySelector('[data-tutorial-kicker]');
  const targetLabel = dialog.querySelector('[data-tutorial-target-label]');
  const description = dialog.querySelector('[data-tutorial-description]');
  const note = dialog.querySelector('[data-tutorial-note]');
  const count = dialog.querySelector('[data-tutorial-count]');
  const progress = dialog.querySelector('[data-tutorial-progress-bar]');
  const progressTrack = dialog.querySelector('.tutorial-progress');
  const back = dialog.querySelector('[data-tutorial-back]');
  const next = dialog.querySelector('[data-tutorial-next]');
  const done = dialog.querySelector('[data-tutorial-done]');
  let current = 0;
  let opener = null;
  let activeTarget = null;
  let savedPagePosition = null;

  const firstMatch = selectors => (Array.isArray(selectors) ? selectors : [selectors])
    .map(selector => document.querySelector(selector)).find(Boolean);

  function getStepTarget(index) {
    const path = location.pathname;
    if (index === 0) return [firstMatch(['.side-nav a[href*="/workspace/"]', '.side-nav a.on', '.profile-summary']), 'Choose Overview'];
    if (index === 1) {
      if (role === 'client') return [firstMatch(['[data-tutorial-target="client-view"]', '#client-job']), 'Choose an event to review'];
      if (role === 'finance') return [firstMatch(['.side-nav a[href*="view=projects"]', 'main nav.tabs a[href*="projects"]']), 'Open Draft bills'];
      if (path === '/imports') return [firstMatch(['[data-tutorial-target="chat-file"]']), 'Choose the WhatsApp text export'];
      return [firstMatch(['main [data-tutorial-target="import"]', 'aside [data-tutorial-target="import"]']), 'Import a chat'];
    }
    if (index === 2) {
      if (path === '/imports') return [firstMatch(['[data-tutorial-target="chat-quote"]']), 'Choose the matching quote'];
      if (path.startsWith('/job/')) return [firstMatch(['.change .show-src']), 'Show the source messages'];
      const project = firstMatch(['[data-tutorial-target="project-open"]']);
      return [project || firstMatch(['.side-nav a[href*="/workspace/"]']), project ? (role === 'finance' ? 'Open a draft bill' : 'Open a project') : 'Return to your workspace'];
    }
    if (index === 3) {
      if (path === '/imports') return [firstMatch(['[data-tutorial-target="find-changes"]']), 'Find changes'];
      if (path.startsWith('/job/')) return [firstMatch(['[data-tutorial-target="change-action"]', '.show-src']), 'Review this change'];
      if (role === 'client') return [firstMatch(['[data-tutorial-target="client-view"]', '#client-job']), 'View changes for an event'];
      if (role === 'finance') return [firstMatch(['.side-nav a[href*="view=activity"]']), 'Open Reconciliation'];
      return [firstMatch(['main nav.tabs a[href*="view=tasks"]', 'main nav.tabs a[href*="projects"]']), role === 'owner' ? 'Open the decision queue' : 'Open your review queue'];
    }
    if (role === 'finance' && !path.startsWith('/job/')) return [firstMatch(['[data-tutorial-target="project-open"]']), 'Open a draft bill'];
    if (path.startsWith('/job/')) return [firstMatch(['[data-tutorial-target="draft-bill"]']), 'Open Draft bill'];
    return [firstMatch(['[data-tutorial-target="guide"]', 'a[href="/guide"]']), 'Open the Workflow guide'];
  }

  function placeCard(targetRect) {
    const margin = 16;
    const width = card.getBoundingClientRect().width;
    const height = card.getBoundingClientRect().height;
    const space = {
      right: innerWidth - targetRect.right - margin * 2,
      left: targetRect.left - margin * 2,
      below: innerHeight - targetRect.bottom - margin * 2,
      above: targetRect.top - margin * 2
    };
    let left = margin;
    let top = margin;
    if (space.right >= width) {
      left = targetRect.right + margin;
      top = Math.min(Math.max(margin, targetRect.top), innerHeight - height - margin);
    } else if (space.left >= width) {
      left = targetRect.left - width - margin;
      top = Math.min(Math.max(margin, targetRect.top), innerHeight - height - margin);
    } else if (space.below >= Math.min(height, 250)) {
      left = Math.min(Math.max(margin, targetRect.left), innerWidth - width - margin);
      top = targetRect.bottom + margin;
    } else {
      left = Math.min(Math.max(margin, targetRect.left), innerWidth - width - margin);
      top = Math.max(margin, targetRect.top - height - margin);
    }
    card.style.left = `${Math.max(margin, Math.min(left, innerWidth - width - margin))}px`;
    card.style.top = `${Math.max(margin, Math.min(top, innerHeight - height - margin))}px`;
  }

  function positionTutorial() {
    if (!dialog.open) return;
    const [target, label] = getStepTarget(current);
    activeTarget = target || document.querySelector('[data-tutorial-open]');
    targetLabel.textContent = label || 'Tutorial button';
    if (!activeTarget) return;
    const beforeScroll = activeTarget.getBoundingClientRect();
    if (beforeScroll.bottom <= 0 || beforeScroll.top >= innerHeight || beforeScroll.right <= 0 || beforeScroll.left >= innerWidth) {
      activeTarget.scrollIntoView({block: 'center', inline: 'nearest'});
    }
    const rect = activeTarget.getBoundingClientRect();
    const pad = 6;
    const left = Math.max(4, rect.left - pad);
    const top = Math.max(4, rect.top - pad);
    spotlight.style.left = `${left}px`;
    spotlight.style.top = `${top}px`;
    spotlight.style.width = `${Math.min(innerWidth - left - 4, rect.width + pad * 2)}px`;
    spotlight.style.height = `${Math.min(innerHeight - top - 4, rect.height + pad * 2)}px`;
    placeCard({left, top, right: left + Math.min(innerWidth - left - 4, rect.width + pad * 2), bottom: top + Math.min(innerHeight - top - 4, rect.height + pad * 2)});
  }

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
    let stepDescription = step.description;
    let stepNote = step.note;
    if (role === 'client' && current === 1) {
      stepDescription = 'Choose an event from the list, then open its changes to respond to each one.';
      stepNote = 'Confirm a change or explain why you dispute it.';
    } else if (role === 'client' && current === 2) {
      stepDescription = 'Review each proposed change alongside the event details before responding.';
    } else if (role === 'finance' && current === 1) {
      stepDescription = 'Open Draft bills to see reconciled totals for each project.';
      stepNote = 'Only client-confirmed changes are included.';
    } else if (role === 'finance' && current === 2) {
      stepDescription = 'Open a project draft to inspect its lines and export a CSV for accounting review.';
    } else if (role === 'finance' && current === 3) {
      stepDescription = 'Open Reconciliation to review the recorded pricing and approval activity.';
    }
    description.textContent = stepDescription;
    note.textContent = stepNote;
    count.textContent = `Step ${current + 1} of ${steps.length}`;
    progress.style.width = `${((current + 1) / steps.length) * 100}%`;
    progressTrack.setAttribute('aria-valuenow', String(current + 1));
    progressTrack.setAttribute('aria-valuemax', String(steps.length));
    back.disabled = current === 0;
    next.hidden = current === steps.length - 1;
    done.hidden = current !== steps.length - 1;
    requestAnimationFrame(positionTutorial);
  }

  function openTutorial(trigger) {
    opener = trigger || document.activeElement;
    savedPagePosition = {
      x: window.scrollX,
      y: window.scrollY,
      rootBehavior: document.documentElement.style.scrollBehavior,
      containers: Array.from(document.querySelectorAll('body *'))
        .filter(element => element.scrollHeight > element.clientHeight || element.scrollWidth > element.clientWidth)
        .map(element => [element, element.scrollTop, element.scrollLeft])
    };
    document.documentElement.style.scrollBehavior = 'auto';
    current = 0;
    renderStep();
    if (!dialog.open) dialog.showModal();
    requestAnimationFrame(positionTutorial);
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
    if (savedPagePosition) {
      window.scrollTo(savedPagePosition.x, savedPagePosition.y);
      savedPagePosition.containers.forEach(([element, top, left]) => {
        if (element.isConnected) { element.scrollTop = top; element.scrollLeft = left; }
      });
      document.documentElement.style.scrollBehavior = savedPagePosition.rootBehavior;
      savedPagePosition = null;
    }
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
  window.addEventListener('resize', positionTutorial);
  window.addEventListener('scroll', positionTutorial, true);

  if (!wasDismissed()) openTutorial(null);
})();
