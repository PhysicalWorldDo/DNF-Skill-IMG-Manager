const data = window.BERSERKER_SKILL_DATA;

const tabButtons = [...document.querySelectorAll(".tab")];
const learnPage = document.querySelector("#learnPage");
const vpPage = document.querySelector("#vpPage");
const skillCanvas = document.querySelector("#skillCanvas");
const skillLayer = document.querySelector("#skillLayer");
const linkLayer = document.querySelector("#linkLayer");
const vpCanvas = document.querySelector("#vpCanvas");
const skillTooltip = document.createElement("div");
skillTooltip.className = "skill-tooltip";
skillTooltip.hidden = true;
skillCanvas.append(skillTooltip);

let selectedSkillButton = null;
let selectedVpButton = null;

function iconSrc(skill) {
  return skill.icon || "";
}

function groupedSkillsByPosition() {
  const groups = new Map();
  data.skills.forEach((skill) => {
    const key = `${skill.x},${skill.y}`;
    if (!groups.has(key)) {
      groups.set(key, []);
    }
    groups.get(key).push(skill);
  });
  return [...groups.values()];
}

function showSkillTooltip(skill) {
  skillTooltip.textContent = skill.name || skill.english || "";
  skillTooltip.style.left = `${skill.x + 44}px`;
  skillTooltip.style.top = `${skill.y + 8}px`;
  skillTooltip.hidden = false;
}

function hideSkillTooltip() {
  skillTooltip.hidden = true;
}

function setTab(tabName) {
  const isLearn = tabName === "learn";
  learnPage.classList.toggle("is-active", isLearn);
  vpPage.classList.toggle("is-active", !isLearn);
  tabButtons.forEach((button) => {
    button.classList.toggle("is-active", button.dataset.tab === tabName);
  });
}

function renderLinks() {
  const maxY = Math.max(...data.skills.map((skill) => skill.y)) + 80;
  linkLayer.setAttribute("viewBox", `0 0 532 ${maxY}`);
  linkLayer.style.height = `${maxY}px`;

  data.links.forEach((link) => {
    const midY = Math.round((link.y1 + link.y2) / 2);
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.classList.add("skill-link");
    path.setAttribute("d", `M ${link.x1} ${link.y1} L ${link.x1} ${midY} L ${link.x2} ${midY} L ${link.x2} ${link.y2}`);
    linkLayer.append(path);
  });
}

function stackPosition(index, total) {
  if (total === 2) {
    return index === 0 ? { x: 0, y: 0 } : { x: 14, y: 14 };
  }

  const positions = [
    { x: 0, y: 0 },
    { x: 14, y: 0 },
    { x: 7, y: 14 },
    { x: 14, y: 14 },
  ];
  return positions[index] || { x: 14, y: 14 };
}

function createSkillButton(skill) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "skill-node";
    button.setAttribute("aria-label", skill.name || skill.english || "skill");

    const frame = document.createElement("div");
    frame.className = "skill-frame";

    const img = document.createElement("img");
    img.src = iconSrc(skill);
    img.alt = "";
    frame.append(img);

    button.append(frame);
    button.addEventListener("click", () => {
      selectedSkillButton?.classList.remove("is-selected");
      selectedSkillButton = button;
      button.classList.add("is-selected");
    });
    button.addEventListener("mouseenter", () => showSkillTooltip(skill));
    button.addEventListener("mouseleave", hideSkillTooltip);
    button.addEventListener("focus", () => showSkillTooltip(skill));
    button.addEventListener("blur", hideSkillTooltip);

    return button;
}

function renderSkills() {
  const maxY = Math.max(...data.skills.map((skill) => skill.y)) + 76;
  skillCanvas.style.minHeight = `${maxY}px`;

  groupedSkillsByPosition().forEach((group) => {
    if (group.length === 1) {
      const skill = group[0];
      const button = createSkillButton(skill);
      button.style.left = `${skill.x}px`;
      button.style.top = `${skill.y}px`;
      skillLayer.append(button);
      return;
    }

    const baseSkill = group[0];
    const stack = document.createElement("div");
    stack.className = `skill-stack stack-size-${Math.min(group.length, 4)}`;
    stack.style.left = `${baseSkill.x}px`;
    stack.style.top = `${baseSkill.y}px`;

    group.forEach((skill, index) => {
      const button = createSkillButton(skill);
      const pos = stackPosition(index, group.length);
      button.classList.add("is-stacked");
      button.style.setProperty("--stack-left", `${pos.x}px`);
      button.style.setProperty("--stack-top", `${pos.y}px`);
      button.style.zIndex = `${index + 1}`;
      stack.append(button);
    });

    skillLayer.append(stack);
  });
}

function renderVpRows() {
  const rowStep = 136;
  const topOffset = 18;
  vpCanvas.style.minHeight = `${topOffset + data.vpSkills.length * rowStep + 20}px`;

  data.vpSkills.forEach((skill, index) => {
    const row = document.createElement("div");
    row.className = "vp-row";
    row.style.top = `${topOffset + index * rowStep}px`;

    const base = document.createElement("div");
    base.className = "vp-base";
    base.innerHTML = `
      <span class="base-icon"><img src="${iconSrc(skill)}" alt=""></span>
      <div class="base-name">${skill.name}</div>
    `;
    row.append(base);

    skill.vp.slice(0, 2).forEach((option, optionIndex) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `vp-option option-${optionIndex + 1}`;
      button.innerHTML = `
        <span class="vp-option-icon"><img src="${iconSrc(skill)}" alt=""></span>
        <div class="vp-option-name">${option.name || option.type}</div>
      `;
      button.addEventListener("click", () => {
        selectedVpButton?.classList.remove("is-selected");
        selectedVpButton = button;
        button.classList.add("is-selected");
      });
      row.append(button);
    });

    vpCanvas.append(row);
  });
}

tabButtons.forEach((button) => {
  button.addEventListener("click", () => setTab(button.dataset.tab));
});

renderLinks();
renderSkills();
renderVpRows();

const firstSkill = data.skills.find((skill) => skill.english === "BloodyVigorous") || data.skills[0];
const firstButton = [...document.querySelectorAll(".skill-node")].find((button) => button.getAttribute("aria-label") === firstSkill.name);
if (firstButton) {
  firstButton.classList.add("is-selected");
  selectedSkillButton = firstButton;
}
