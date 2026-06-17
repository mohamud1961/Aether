import { byId, escapeHtml, setText } from "./dom.mjs";
import { t } from "./i18n.mjs";

function skillCard(skill) {
  return `
    <article class="skill-card">
      <div class="skill-card-head">
        <div>
          <strong>${escapeHtml(skill.name || skill.id || "Skill")}</strong>
          <p class="skill-card-meta">${escapeHtml(skill.source || "unknown")}</p>
        </div>
        <button class="ghost" data-skill-open="${escapeHtml(skill.path)}">${escapeHtml(t("common.openFolder"))}</button>
      </div>
      <p class="section-copy">${escapeHtml(skill.description || t("skills.noDescription"))}</p>
      <p class="skill-card-path">${escapeHtml(skill.path || "")}</p>
    </article>
  `;
}

export function renderSkillsState(state) {
  const list = byId("skills-list");
  if (!list) {
    return;
  }

  const skills = state.skills?.skills || [];
  if (!skills.length) {
    list.innerHTML = `
      <article class="skill-card skill-card-empty">
        <strong>${escapeHtml(t("skills.noSkillsTitle"))}</strong>
        <p class="section-copy">${escapeHtml(t("skills.noSkillsBody"))}</p>
      </article>
    `;
    setText(byId("skills-status"), t("skills.noSkillsTitle"));
    return;
  }

  list.innerHTML = skills.map(skillCard).join("");
  setText(byId("skills-status"), t("skills.availableCount", { count: skills.length, suffix: skills.length === 1 ? "" : "s" }));
}

export function bindSkillsActions({ state, onReload, onOpenPath }) {
  byId("reload-skills")?.addEventListener("click", onReload);
  byId("open-workspace-skills")?.addEventListener("click", () => {
    onOpenPath(state.skills?.workspace_skill_dir);
  });
  byId("skills-list")?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-skill-open]");
    if (!button) {
      return;
    }
    onOpenPath(button.dataset.skillOpen);
  });
}
