import { byId, escapeHtml, setText } from "./dom.mjs";
import { t } from "./i18n.mjs";

function summarizeSchedule(schedule) {
  const type = String(schedule.schedule_type || "").trim();
  const value = String(schedule.schedule_value || "").trim();
  if (!type && !value) {
    return t("schedules.unknownSchedule");
  }
  if (type === "cron") {
    return `Cron · ${value}`;
  }
  if (type === "date") {
    return `${t("schedules.oneTime")} · ${value}`;
  }
  return `${type || t("schedules.scheduleLabel").toLowerCase()} · ${value}`;
}

function summarizePrompt(text) {
  const normalized = String(text || "").replace(/\s+/g, " ").trim();
  if (!normalized) {
    return t("schedules.noPromptText");
  }
  if (normalized.length <= 140) {
    return normalized;
  }
  return `${normalized.slice(0, 137).trimEnd()}...`;
}

function scheduleMeta(schedule) {
  const parts = [];
  if (schedule.channel_target) {
    const channelLabel = schedule.channel_type === "telegram"
      ? "Telegram"
      : schedule.channel_type === "discord"
        ? "Discord"
        : "Slack";
    parts.push(`${channelLabel} ${schedule.channel_target}`);
  }
  if (schedule.user) {
    parts.push(t("schedules.userLabel", { user: schedule.user }));
  }
  return parts.join(" · ");
}

export function renderSchedulesState(state) {
  const list = byId("schedule-list");
  if (!list) {
    return;
  }

  if (state.scheduleError) {
    list.innerHTML = `
      <article class="simple-item">
        <strong>${escapeHtml(t("schedules.loadFailedTitle"))}</strong>
        <p>${escapeHtml(state.scheduleError)}</p>
      </article>
    `;
    setText(byId("schedule-status"), t("schedules.loadFailed", { message: state.scheduleError }));
    return;
  }

  if (!state.schedules.length) {
    list.innerHTML = `
      <article class="simple-item">
        <strong>${escapeHtml(t("schedules.noSchedulesTitle"))}</strong>
        <p>${escapeHtml(t("schedules.noSchedulesBody"))}</p>
      </article>
    `;
    setText(byId("schedule-status"), t("schedules.noSchedulesConfigured"));
    return;
  }

  list.innerHTML = state.schedules.map((schedule) => `
    <article class="simple-item">
      <div class="schedule-card-head">
        <strong>${escapeHtml(String(schedule.name || schedule.id || t("schedules.scheduleLabel")))}</strong>
        <span class="status-chip ${schedule.is_enabled !== false ? "online" : "offline"}">${schedule.is_enabled !== false ? escapeHtml(t("common.enabled")) : escapeHtml(t("common.disabled"))}</span>
      </div>
      <p>${escapeHtml(summarizePrompt(schedule.text || ""))}</p>
      <p class="schedule-card-meta">${escapeHtml(summarizeSchedule(schedule))}${scheduleMeta(schedule) ? ` · ${escapeHtml(scheduleMeta(schedule))}` : ""}</p>
    </article>
  `).join("");

  const fileSuffix = state.scheduleFile ? ` · ${state.scheduleFile}` : "";
  setText(
    byId("schedule-status"),
    t("schedules.loadedCount", {
      count: state.schedules.length,
      suffix: state.schedules.length === 1 ? "" : "s",
      fileSuffix,
    }),
  );
}

export function bindScheduleActions({ onReload }) {
  byId("reload-schedules")?.addEventListener("click", onReload);
}
