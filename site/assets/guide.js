"use strict";

(() => {
  const prefix = "ashleys-bed:left-only-2026-09:";
  const controls = [...document.querySelectorAll("[data-check], [data-field]")];
  const checks = controls.filter((control) => control.matches("[data-check]"));
  const status = document.querySelector("#save-status");
  let storageAvailable = true;

  function updateProgress() {
    if (!controls.length) return;
    document.querySelector("#personal-progress").hidden = false;
    const completed = checks.filter((input) => input.checked).length;
    document.querySelector("#progress-label").textContent = checks.length
      ? `${completed} of ${checks.length} personal planning checks completed on this page`
      : "Your CNC setup worksheet";
    const progress = document.querySelector("#check-progress");
    progress.hidden = !checks.length;
    progress.max = checks.length || 1;
    progress.value = completed;
    status.textContent = storageAvailable
      ? "Your checks and notes save only in this browser. Checking a box does not approve machining."
      : "Browser storage is unavailable. Export your notes before leaving this page.";
  }

  controls.forEach((control) => {
    const key = prefix + (control.dataset.check || control.dataset.field);
    try {
      const value = localStorage.getItem(key);
      if (value !== null) {
        if (control.type === "checkbox") control.checked = value === "true";
        else control.value = value;
      }
    } catch {
      storageAvailable = false;
    }
    control.addEventListener("input", () => {
      try {
        localStorage.setItem(
          key,
          control.type === "checkbox" ? String(control.checked) : control.value,
        );
      } catch {
        storageAvailable = false;
      }
      updateProgress();
    });
  });
  updateProgress();

  const printFields = controls
    .filter((control) => control.hasAttribute("data-field"))
    .map((control) => {
      const value = document.createElement("span");
      value.className = "print-value";
      value.setAttribute("aria-hidden", "true");
      control.after(value);
      return { control, value };
    });
  let openedForPrint = [];
  window.addEventListener("beforeprint", () => {
    printFields.forEach(({ control, value }) => {
      value.textContent = control.value || "Not recorded";
    });
    openedForPrint = [...document.querySelectorAll("details:not([open])")];
    openedForPrint.forEach((details) => {
      details.open = true;
    });
  });
  window.addEventListener("afterprint", () => {
    openedForPrint.forEach((details) => {
      details.open = false;
    });
    openedForPrint = [];
  });

  document
    .querySelector("#print-page")
    .addEventListener("click", () => window.print());
  document.querySelector("#export-notes").addEventListener("click", () => {
    const notes = {};
    try {
      for (let index = 0; index < localStorage.length; index += 1) {
        const key = localStorage.key(index);
        if (key.startsWith(prefix))
          notes[key.slice(prefix.length)] = localStorage.getItem(key);
      }
    } catch {
      storageAvailable = false;
    }
    controls.forEach((control) => {
      notes[control.dataset.check || control.dataset.field] =
        control.type === "checkbox" ? control.checked : control.value;
    });
    const payload = {
      project: "Ashley’s bed — bed + left bookcase",
      revision: "2026-09-22",
      exportedAt: new Date().toISOString(),
      notice:
        "Personal planning notes only. Not a fabrication approval or machining release.",
      notes,
    };
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(payload, null, 2)], {
        type: "application/json",
      }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = "ashleys-bed-planning-notes.json";
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    updateProgress();
  });

  const search = document.querySelector("#bom-search");
  if (search) {
    search.addEventListener("input", () => {
      const query = search.value.trim().toLocaleLowerCase();
      const rows = [...document.querySelectorAll("[data-bom-row]")];
      rows.forEach((row) => {
        row.hidden = !row.textContent.toLocaleLowerCase().includes(query);
      });
      document.querySelectorAll("[data-bom-group]").forEach((group) => {
        group.hidden = ![...group.querySelectorAll("[data-bom-row]")].some(
          (row) => !row.hidden,
        );
      });
      document.querySelector("#bom-empty").hidden = rows.some(
        (row) => !row.hidden,
      );
    });
  }

  const model = document.querySelector("#bed-model");
  const modelButtons = [...document.querySelectorAll("[data-model]")];
  modelButtons.forEach((button) => {
    button.addEventListener("click", () => {
      model.poster = button.dataset.poster;
      model.querySelector("[slot=poster]").src = button.dataset.poster;
      model.src = button.dataset.model;
      modelButtons.forEach((other) =>
        other.setAttribute("aria-pressed", String(other === button)),
      );
    });
  });
})();
