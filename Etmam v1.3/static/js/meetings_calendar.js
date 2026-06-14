(function () {
  'use strict';

  let calendar = null;
  let currentMeetingId = null;

  function todayISO() {
    const d = new Date();
    const off = d.getTimezoneOffset();
    const local = new Date(d.getTime() - off * 60 * 1000);
    return local.toISOString().substring(0, 10);
  }

  function nowLocalISO() {
    const d = new Date();
    const off = d.getTimezoneOffset();
    const local = new Date(d.getTime() - off * 60 * 1000);
    return local.toISOString().substring(0, 16);
  }

  function initCalendar() {
    const el = document.getElementById('meetings-calendar');
    if (!el || typeof FullCalendar === 'undefined') return;

    calendar = new FullCalendar.Calendar(el, {
      initialView: 'dayGridMonth',
      headerToolbar: {
        left:   'prev,next today',
        center: 'title',
        right:  'dayGridMonth,timeGridWeek,timeGridDay',
      },
      height: 'auto',
      navLinks: true,
      nowIndicator: true,
      eventTimeFormat: { hour: 'numeric', minute: '2-digit', meridiem: 'short' },
      events: '/meetings/api/events/',
      dateClick: function (info) {
        const clicked = info.dateStr.substring(0, 10);
        if (clicked < todayISO()) {
          return;
        }
        const dateInput = document.getElementById('schedule-date');
        if (dateInput) dateInput.value = clicked;
        openScheduleModal();
      },
      eventClick: function (info) {
        info.jsEvent.preventDefault();
        openMeetingModal(info.event.id);
      },
    });

    calendar.render();
  }

  window.openScheduleModal = function () {
    const m = document.getElementById('schedule-modal');
    if (!m) return;
    m.classList.add('open');

    const today = todayISO();
    const d = document.getElementById('schedule-date');
    if (d) {
      d.min = today;
      if (!d.value || d.value < today) d.value = today;
    }

    const t = document.getElementById('schedule-time');
    function syncTimeMin() {
      if (!t || !d) return;
      if (d.value === today) {
        const now = new Date();
        const hh = String(now.getHours()).padStart(2, '0');
        const mm = String(now.getMinutes()).padStart(2, '0');
        t.min = hh + ':' + mm;
      } else {
        t.removeAttribute('min');
      }
    }
    if (d) {
      d.removeEventListener('change', syncTimeMin);
      d.addEventListener('change', syncTimeMin);
    }
    syncTimeMin();
  };

  window.closeScheduleModal = function () {
    const m = document.getElementById('schedule-modal');
    if (m) m.classList.remove('open');
  };

  window.openMeetingModal = function (meetingId) {
    currentMeetingId = meetingId;
    const modal = document.getElementById('meeting-modal');
    const content = document.getElementById('meeting-modal-content');
    if (!modal || !content) return;
    content.innerHTML = '<p class="muted" style="padding:2rem;text-align:center;">Loading…</p>';
    modal.classList.add('open');

    fetch('/meetings/' + meetingId + '/?modal=1', { credentials: 'same-origin' })
      .then(r => r.text())
      .then(html => { content.innerHTML = html; })
      .catch(() => { content.innerHTML = '<p style="padding:2rem;color:#ef4444;">Failed to load meeting.</p>'; });
  };

  window.closeMeetingModal = function () {
    const m = document.getElementById('meeting-modal');
    if (m) m.classList.remove('open');
    currentMeetingId = null;
  };

  window.openRescheduleModal = function (meetingId) {
    const modal = document.getElementById('reschedule-modal');
    if (!modal) return;
    document.getElementById('reschedule-form').action = '/meetings/' + meetingId + '/reschedule/';
    const minNow = nowLocalISO();
    document.querySelectorAll('.reschedule-slot').forEach(function (inp) {
      inp.min = minNow;
    });
    modal.classList.add('open');
  };

  window.closeRescheduleModal = function () {
    const m = document.getElementById('reschedule-modal');
    if (m) m.classList.remove('open');
  };

  document.addEventListener('DOMContentLoaded', function () {
    initCalendar();

    document.querySelectorAll('[onclick*="showSection"]').forEach(btn => {
      btn.addEventListener('click', function () {
        setTimeout(function () {
          if (calendar) calendar.updateSize();
        }, 50);
      });
    });

    const params = new URLSearchParams(window.location.search);
    const mid = params.get('meeting');
    if (mid) {
      const meetingsBtn = document.querySelector('[onclick*="\'meetings\'"]');
      if (meetingsBtn) meetingsBtn.click();
      setTimeout(function () { openMeetingModal(mid); }, 150);
    }
  });
})();
