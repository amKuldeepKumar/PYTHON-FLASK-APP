(function () {
  function el(id) {
    return document.getElementById(id);
  }

  function escapeHtml(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function renderMessages(container, messages) {
    if (!container) return;
    if (!messages || !messages.length) {
      container.innerHTML = '<div class="student-chat-empty">No messages yet. Start with one kind course-related message.</div>';
      return;
    }
    container.innerHTML = messages.map(function (message) {
      return (
        '<article class="student-chat-message' + (message.is_self ? ' is-self' : '') + '">' +
          '<div class="student-chat-message-head">' +
            '<strong>' + escapeHtml(message.sender_name) + '</strong>' +
            '<span>' + escapeHtml(message.created_at) + '</span>' +
          '</div>' +
          '<div>' + escapeHtml(message.body) + '</div>' +
        '</article>'
      );
    }).join('');
    container.scrollTop = container.scrollHeight;
  }

  async function fetchPayload(root, courseId) {
    const url = new URL(root.dataset.fetchUrl, window.location.origin);
    if (courseId) url.searchParams.set('course_id', courseId);
    const response = await fetch(url.toString(), { credentials: 'same-origin' });
    return response.json();
  }

  document.addEventListener('DOMContentLoaded', function () {
    const root = el('studentChatWidget');
    if (!root) return;

    const toggle = el('studentChatToggle');
    const close = el('studentChatClose');
    const panel = el('studentChatPanel');
    const select = el('studentChatCourseSelect');
    const notice = el('studentChatNotice');
    const messages = el('studentChatMessages');
    const form = el('studentChatForm');
    const textarea = el('studentChatBody');

    function openPanel() {
      root.classList.add('is-open');
      panel.setAttribute('aria-hidden', 'false');
    }

    function closePanel() {
      root.classList.remove('is-open');
      panel.setAttribute('aria-hidden', 'true');
    }

    async function refresh(courseId) {
      const payload = await fetchPayload(root, courseId || select.value);
      if (!payload.ok) return;
      if (payload.moderation_notice && notice) {
        notice.textContent = payload.moderation_notice;
      }
      renderMessages(messages, payload.messages || []);
    }

    toggle?.addEventListener('click', function () {
      if (root.classList.contains('is-open')) {
        closePanel();
      } else {
        openPanel();
      }
    });

    close?.addEventListener('click', closePanel);

    select?.addEventListener('change', function () {
      refresh(select.value);
    });

    form?.addEventListener('submit', async function (event) {
      event.preventDefault();
      const body = (textarea?.value || '').trim();
      if (!body) return;

      const formData = new FormData();
      formData.append('csrf_token', root.dataset.csrfToken || '');
      formData.append('course_id', select.value);
      formData.append('body', body);

      const response = await fetch(root.dataset.postUrl, {
        method: 'POST',
        body: formData,
        credentials: 'same-origin',
      });
      const payload = await response.json();
      if (!payload.ok) {
        if (notice) notice.textContent = payload.message || 'Message blocked.';
        return;
      }

      textarea.value = '';
      await refresh(select.value);
      if (notice) {
        notice.textContent = 'Message sent. Keep your course chat kind and learning-focused.';
      }
    });

    renderMessages(messages, []);
    refresh(root.dataset.initialCourseId || select?.value || '');
  });
})();
