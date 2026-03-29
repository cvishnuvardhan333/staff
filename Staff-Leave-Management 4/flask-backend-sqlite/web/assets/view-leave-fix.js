(function () {
  const TOKEN_KEY = "ssls_token";
  const THEME_KEY = "ssls_theme";
  const LEAVES_ENDPOINT = `${window.location.origin}/api/leaves/me`;
  const NOTIFICATIONS_ENDPOINT = `${window.location.origin}/api/notifications/me`;
  const NOTIFICATIONS_CLEAR_ENDPOINT = `${window.location.origin}/api/notifications/clear`;
  const DISMISSED_NOTIFICATIONS_KEY = "ssls_dismissed_notifications";
  const NAVIGATION_EVENT = "staff-leave-fix:navigation";
  const CACHE_TTL_MS = 5000;

  let cachedLeaves = null;
  let cachedAt = 0;
  let cachedNotifications = null;
  let cachedNotificationsAt = 0;
  let patchTimer = null;
  let observer = null;
  let clockInterval = null;
  let clearNotificationsInFlight = false;

  function getTheme() {
    return window.localStorage.getItem(THEME_KEY) || "light";
  }

  function applyTheme(theme) {
    window.localStorage.setItem(THEME_KEY, theme);
    document.documentElement.classList.toggle("dark", theme === "dark");
  }

  function toggleTheme() {
    const nextTheme = getTheme() === "dark" ? "light" : "dark";
    applyTheme(nextTheme);
    patchAuthThemeToggle();
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function getHeadingPanel(title) {
    const headings = Array.from(document.querySelectorAll("h3"));
    const heading = headings.find((node) => node.textContent.trim() === title);
    return heading ? heading.closest(".glass-card") : null;
  }

  function readLeaveStatusFilters(panel) {
    const searchInput = panel.querySelector('input[placeholder="Search leave"]');
    const statusSelect = panel.querySelector("select");

    return {
      search: (searchInput?.value || "").trim().toLowerCase(),
      status: statusSelect?.value || "all",
    };
  }

  function filterLeaves(leaves, filters) {
    return leaves
      .filter((leave) => {
        const haystack = [leave.type, leave.status, leave.reason]
          .join(" ")
          .toLowerCase();
        return haystack.includes(filters.search);
      })
      .filter((leave) => filters.status === "all" || leave.status === filters.status);
  }

  function authorizedFetch(url, options) {
    const token = window.localStorage.getItem(TOKEN_KEY);
    const headers = {
      ...(options?.headers || {}),
    };

    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }

    return window.fetch(url, {
      ...(options || {}),
      headers,
    });
  }

  function getDismissedNotificationIds() {
    try {
      const raw = window.localStorage.getItem(DISMISSED_NOTIFICATIONS_KEY);
      const parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed.map(String) : [];
    } catch (_error) {
      return [];
    }
  }

  function setDismissedNotificationIds(ids) {
    const normalized = Array.from(new Set((ids || []).map(String)));
    window.localStorage.setItem(
      DISMISSED_NOTIFICATIONS_KEY,
      JSON.stringify(normalized),
    );
  }

  function clearDismissedNotificationIds() {
    window.localStorage.removeItem(DISMISSED_NOTIFICATIONS_KEY);
  }

  function filterVisibleNotifications(notifications) {
    const dismissed = new Set(getDismissedNotificationIds());
    return notifications.filter((notification) => !dismissed.has(String(notification._id ?? notification.id)));
  }

  async function fetchLeaves() {
    const now = Date.now();
    if (cachedLeaves && now - cachedAt < CACHE_TTL_MS) {
      return cachedLeaves;
    }

    const token = window.localStorage.getItem(TOKEN_KEY);
    if (!token) {
      return cachedLeaves || [];
    }

    const response = await authorizedFetch(LEAVES_ENDPOINT);

    if (!response.ok) {
      throw new Error(`Failed to load leaves: ${response.status}`);
    }

    const payload = await response.json();
    cachedLeaves = Array.isArray(payload) ? payload : [];
    cachedAt = now;
    return cachedLeaves;
  }

  async function fetchNotifications() {
    const now = Date.now();
    if (cachedNotifications && now - cachedNotificationsAt < CACHE_TTL_MS) {
      return cachedNotifications;
    }

    const token = window.localStorage.getItem(TOKEN_KEY);
    if (!token) {
      return cachedNotifications || [];
    }

    const response = await authorizedFetch(NOTIFICATIONS_ENDPOINT);
    if (!response.ok) {
      throw new Error(`Failed to load notifications: ${response.status}`);
    }

    const payload = await response.json();
    cachedNotifications = Array.isArray(payload) ? payload : [];
    cachedNotificationsAt = now;
    return cachedNotifications;
  }

  function ensureReasonHeaderCell(headerRow) {
    if (!headerRow) {
      return null;
    }

    const cells = Array.from(headerRow.children);
    const existing = cells.find((cell) => cell.textContent.trim() === "Reason");
    if (existing) {
      return existing;
    }

    const cell = document.createElement("th");
    cell.className = "py-3 px-4 staff-leave-fix-header-reason";
    cell.textContent = "Reason";
    headerRow.appendChild(cell);
    return cell;
  }

  function setReasonCellContent(cell, reason, compact) {
    if (!cell) {
      return;
    }

    const safeReason = reason && String(reason).trim()
      ? String(reason).trim()
      : "No reason provided";

    cell.className = compact
      ? "py-3 px-4 text-slate-500 staff-leave-fix-reason-cell"
      : "py-3 px-4 text-slate-500 staff-leave-fix-reason-cell";
    cell.innerHTML = [
      `<span class="staff-leave-fix-inline-reason${compact ? " staff-leave-fix-inline-reason-compact" : ""}"`,
      ` title="${escapeHtml(safeReason)}">`,
      `${escapeHtml(safeReason)}`,
      "</span>",
    ].join("");
  }

  function patchLeaveStatusTable(leaves) {
    if (window.location.pathname !== "/leave/status") {
      return;
    }

    const panel = getHeadingPanel("Leave Status");
    const table = panel?.querySelector("table");
    const headerRow = table?.querySelector("thead tr");
    const bodyRows = table ? Array.from(table.querySelectorAll("tbody tr")) : [];

    if (!panel || !table || !headerRow || bodyRows.length === 0) {
      return;
    }

    const headerCells = Array.from(headerRow.children);
    if (headerCells[4]) {
      headerCells[4].textContent = "Reason";
      headerCells[4].classList.add("staff-leave-fix-header-reason");
    }

    const filteredLeaves = filterLeaves(leaves, readLeaveStatusFilters(panel));
    bodyRows.forEach((row, index) => {
      const leave = filteredLeaves[index];
      const cells = Array.from(row.children);
      const reasonCell = cells[4];
      if (!reasonCell) {
        return;
      }

      setReasonCellContent(reasonCell, leave?.reason, false);
    });
  }

  function patchDashboardTable(leaves) {
    if (window.location.pathname !== "/dashboard") {
      return;
    }

    const panel = getHeadingPanel("Leave History");
    const table = panel?.querySelector("table");
    const headerRow = table?.querySelector("thead tr");
    const bodyRows = table ? Array.from(table.querySelectorAll("tbody tr")) : [];

    if (!panel || !table || !headerRow || bodyRows.length === 0) {
      return;
    }

    ensureReasonHeaderCell(headerRow);
    const recentLeaves = leaves.slice(0, 6);

    bodyRows.forEach((row, index) => {
      const leave = recentLeaves[index];
      let reasonCell = row.children[3];

      if (!reasonCell) {
        reasonCell = document.createElement("td");
        row.appendChild(reasonCell);
      }

      setReasonCellContent(reasonCell, leave?.reason, true);
    });
  }

  function clearClockInterval() {
    if (clockInterval) {
      window.clearInterval(clockInterval);
      clockInterval = null;
    }
  }

  function formatClockParts() {
    const now = new Date();
    return {
      time: now.toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      }),
      date: now.toLocaleDateString([], {
        weekday: "long",
        year: "numeric",
        month: "long",
        day: "numeric",
      }),
      zone: Intl.DateTimeFormat().resolvedOptions().timeZone || "Local time",
    };
  }

  function updateClockCard() {
    const clock = document.querySelector(".staff-leave-fix-clock");
    if (!clock || window.location.pathname !== "/calendar") {
      clearClockInterval();
      return;
    }

    const parts = formatClockParts();
    const timeNode = clock.querySelector(".staff-leave-fix-clock-time");
    const metaNode = clock.querySelector(".staff-leave-fix-clock-meta");
    if (timeNode) {
      timeNode.textContent = parts.time;
    }
    if (metaNode) {
      metaNode.textContent = `${parts.date} • ${parts.zone}`;
    }
  }

  function patchCalendarClock() {
    if (window.location.pathname !== "/calendar") {
      clearClockInterval();
      return;
    }

    const headings = Array.from(document.querySelectorAll("h3"));
    const introHeading = headings.find((node) => {
      if (node.textContent.trim() !== "Calendar") {
        return false;
      }

      const description = node.parentElement?.querySelector("p");
      return description?.textContent?.includes("upcoming leave days");
    });

    const introPanel = introHeading?.parentElement;
    if (!introPanel) {
      return;
    }

    let clock = introPanel.querySelector(".staff-leave-fix-clock");
    if (!clock) {
      clock = document.createElement("div");
      clock.className = "staff-leave-fix-clock glass-card";
      clock.innerHTML = [
        '<p class="staff-leave-fix-clock-label">Current Time</p>',
        '<p class="staff-leave-fix-clock-time"></p>',
        '<p class="staff-leave-fix-clock-meta"></p>',
      ].join("");
      introPanel.appendChild(clock);
    }

    updateClockCard();
    if (!clockInterval) {
      clockInterval = window.setInterval(updateClockCard, 1000);
    }
  }

  function isAuthPage() {
    return [
      "/login",
      "/register",
      "/forgot-password",
      "/reset-password",
    ].includes(window.location.pathname);
  }

  function patchAuthThemeToggle() {
    if (!isAuthPage()) {
      return;
    }

    const shell = document.querySelector(".app-shell");
    if (!shell) {
      return;
    }

    let toggle = document.querySelector(".staff-leave-fix-auth-theme-toggle");
    if (!toggle) {
      toggle = document.createElement("button");
      toggle.type = "button";
      toggle.className = "staff-leave-fix-auth-theme-toggle";
      toggle.addEventListener("click", toggleTheme);
      shell.appendChild(toggle);
    }

    const theme = getTheme();
    toggle.setAttribute("aria-label", theme === "dark" ? "Switch to light mode" : "Switch to dark mode");
    toggle.innerHTML = [
      '<span class="staff-leave-fix-auth-theme-icon" aria-hidden="true">',
      theme === "dark" ? "☀" : "☾",
      "</span>",
      `<span class="staff-leave-fix-auth-theme-text">${theme === "dark" ? "Light Mode" : "Dark Mode"}</span>`,
    ].join("");
  }

  function createNotificationsEmptyState(text) {
    const node = document.createElement("p");
    node.className = "text-sm text-slate-500 staff-leave-fix-notifications-empty";
    node.textContent = text;
    return node;
  }

  function patchNotificationList(listContainer, notifications) {
    if (!listContainer) {
      return;
    }

    const visibleNotifications = filterVisibleNotifications(notifications);
    const cards = Array.from(listContainer.children).filter((node) =>
      node.classList?.contains("glass-card"),
    );

    cards.forEach((card, index) => {
      const notification = notifications[index];
      const id = notification ? String(notification._id ?? notification.id) : null;
      card.style.display = id && visibleNotifications.some((item) => String(item._id ?? item.id) === id)
        ? ""
        : "none";
    });

    const visibleCards = cards.filter((card) => card.style.display !== "none");
    const existingEmpty = listContainer.querySelector(".staff-leave-fix-notifications-empty");

    if (visibleNotifications.length === 0 && !existingEmpty) {
      listContainer.appendChild(createNotificationsEmptyState("No notifications yet."));
    }

    if (visibleNotifications.length > 0 && existingEmpty) {
      existingEmpty.remove();
    }

    if (visibleCards.length === 0 && cards.length === 0 && !existingEmpty) {
      listContainer.appendChild(createNotificationsEmptyState("No notifications yet."));
    }
  }

  function patchNotificationBadge(notifications) {
    const bellButton = document.querySelector("button.glass-nav.rounded-full.p-3.relative");
    if (!bellButton) {
      return;
    }

    const badge = bellButton.querySelector("span.absolute");
    const unreadCount = filterVisibleNotifications(notifications).filter((item) => !item.isRead).length;

    if (unreadCount <= 0) {
      if (badge) {
        badge.remove();
      }
      return;
    }

    if (badge) {
      badge.textContent = String(unreadCount);
    }
  }

  function applyNotificationFallbackClear(notifications) {
    const ids = notifications.map((notification) => String(notification._id ?? notification.id));
    setDismissedNotificationIds(ids);
    cachedNotifications = notifications;
    cachedNotificationsAt = Date.now();
    schedulePatch();
  }

  async function clearAllNotifications() {
    if (clearNotificationsInFlight) {
      return;
    }

    if (!window.confirm("Clear all notifications?")) {
      return;
    }

    clearNotificationsInFlight = true;
    try {
      let response = await authorizedFetch(NOTIFICATIONS_CLEAR_ENDPOINT, {
        method: "POST",
      });

      if (!response.ok && (response.status === 404 || response.status === 405)) {
        response = await authorizedFetch(NOTIFICATIONS_ENDPOINT, {
          method: "DELETE",
        });
      }

      if (!response.ok) {
        throw new Error(`Failed to clear notifications: ${response.status}`);
      }

      clearDismissedNotificationIds();
      window.location.reload();
    } catch (_error) {
      try {
        const notifications = await fetchNotifications();
        applyNotificationFallbackClear(notifications);
      } catch (_secondaryError) {
        window.alert("Unable to clear notifications right now.");
      }
    } finally {
      clearNotificationsInFlight = false;
    }
  }

  function buildClearAllButton(extraClassName) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `staff-leave-fix-clear-button${extraClassName ? ` ${extraClassName}` : ""}`;
    button.textContent = "Clear All";
    button.addEventListener("click", clearAllNotifications);
    return button;
  }

  function patchNotificationsPage(notifications) {
    if (window.location.pathname !== "/notifications") {
      return;
    }

    const headings = Array.from(document.querySelectorAll("h3"));
    const heading = headings.find((node) => node.textContent.trim() === "Notifications");
    const headerRow = heading?.parentElement?.parentElement;
    if (!headerRow) {
      return;
    }

    let actions = headerRow.querySelector(".staff-leave-fix-notification-actions");
    if (!actions) {
      actions = document.createElement("div");
      actions.className = "staff-leave-fix-notification-actions";
      headerRow.appendChild(actions);
    }

    if (!actions.querySelector(".staff-leave-fix-clear-button")) {
      actions.appendChild(buildClearAllButton());
    }

    const listContainer = headerRow.nextElementSibling;
    patchNotificationList(listContainer, notifications);
  }

  function patchNotificationDropdown(notifications) {
    const labels = Array.from(document.querySelectorAll("p"));
    const label = labels.find((node) => node.textContent.trim() === "Notifications");
    const popup = label?.closest(".glass-card");
    if (!label || !popup) {
      patchNotificationBadge(notifications);
      return;
    }

    let header = popup.querySelector(".staff-leave-fix-dropdown-header");
    if (!header) {
      header = document.createElement("div");
      header.className = "staff-leave-fix-dropdown-header";
      popup.insertBefore(header, popup.firstChild);
      header.appendChild(label);
      header.appendChild(buildClearAllButton("staff-leave-fix-clear-button-compact"));
    }

    const listContainer = popup.querySelector(".mt-3.space-y-3");
    patchNotificationList(listContainer, notifications);
    patchNotificationBadge(notifications);
  }

  async function applyPatches() {
    const path = window.location.pathname;
    patchAuthThemeToggle();
    patchCalendarClock();
    try {
      const notifications = await fetchNotifications();
      patchNotificationsPage(notifications);
      patchNotificationDropdown(notifications);
    } catch (_error) {
      patchNotificationsPage([]);
      patchNotificationDropdown([]);
    }

    if (path === "/leave/status" || path === "/dashboard") {
      try {
        const leaves = await fetchLeaves();
        patchLeaveStatusTable(leaves);
        patchDashboardTable(leaves);
      } catch (_error) {
        patchLeaveStatusTable([]);
        patchDashboardTable([]);
      }
    }
  }

  function schedulePatch() {
    window.clearTimeout(patchTimer);
    patchTimer = window.setTimeout(() => {
      applyPatches();
    }, 80);
  }

  function resetPatchState() {
    cachedLeaves = null;
    cachedAt = 0;
    cachedNotifications = null;
    cachedNotificationsAt = 0;
    clearClockInterval();
    schedulePatch();
  }

  function patchHistoryMethod(methodName) {
    const original = window.history[methodName];
    if (typeof original !== "function") {
      return;
    }

    window.history[methodName] = function patchedHistoryMethod() {
      const result = original.apply(this, arguments);
      window.dispatchEvent(new Event(NAVIGATION_EVENT));
      return result;
    };
  }

  function startObserver() {
    const root = document.getElementById("root");
    if (!root || observer) {
      return;
    }

    observer = new MutationObserver(() => {
      schedulePatch();
    });

    observer.observe(root, {
      childList: true,
      subtree: true,
    });
  }

  document.addEventListener("input", schedulePatch, true);
  document.addEventListener("change", schedulePatch, true);
  window.addEventListener("load", schedulePatch);
  window.addEventListener("popstate", resetPatchState);
  window.addEventListener(NAVIGATION_EVENT, resetPatchState);
  patchHistoryMethod("pushState");
  patchHistoryMethod("replaceState");
  startObserver();
  schedulePatch();
})();
