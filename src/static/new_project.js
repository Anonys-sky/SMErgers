(() => {
  "use strict";
  const form = document.getElementById("new-project-form");
  if (!form) return;
  const status = document.getElementById("project-row-status");
  const groups = {
    quote: document.getElementById("quote-lines"),
    extra: document.getElementById("extra-lines")
  };
  function refresh(kind) {
    const rows = groups[kind].querySelectorAll(".project-line");
    rows.forEach((row, index) => {
      const title = `${kind === "quote" ? "Quote" : "Rate-card"} item ${index + 1}`;
      row.querySelector("[data-line-title]").textContent = title;
      const remove = row.querySelector("[data-remove-line]");
      remove.disabled = kind === "quote" && rows.length === 1;
      remove.setAttribute("aria-label", `Remove ${title.toLowerCase()}`);
    });
    if (kind === "extra") document.getElementById("extra-empty").hidden = rows.length > 0;
  }
  function makeRow(kind) {
    const row = document.createElement("div");
    row.className = "project-line";
    const head = document.createElement("div");
    head.className = "project-line-head";
    const title = document.createElement("strong");
    title.dataset.lineTitle = "";
    const remove = document.createElement("button");
    remove.type = "button";
    remove.dataset.removeLine = "";
    remove.textContent = "Remove";
    head.append(title, remove);
    const fields = document.createElement("div");
    fields.className = "project-line-fields";
    const definitions = kind === "quote"
      ? [["Item name", "item"], ["Quantity", "qty", "number"], ["Unit", "unit"], ["Unit price (RM)", "unit_price", "number"], ["Chat aliases", "aliases"]]
      : [["Item name", "extra_item"], ["Unit", "extra_unit"], ["Unit price (RM)", "extra_price", "number"], ["Chat aliases", "extra_aliases"]];
    definitions.forEach(([text, name, type]) => {
      const label = document.createElement("label");
      label.textContent = text;
      const input = document.createElement("input");
      input.name = name;
      input.type = type || "text";
      if (name.endsWith("aliases")) {
        label.className = "aliases-field";
        const help = document.createElement("span");
        help.className = "field-help";
        help.textContent = "Optional · comma separated; item name included automatically";
        label.append(help);
      } else {
        input.required = true;
      }
      if (type === "number") {
        input.min = name === "qty" ? "0.000001" : "0";
        input.step = name === "qty" ? "any" : "0.01";
        if (name === "qty") input.value = "1";
      }
      label.append(input);
      fields.append(label);
    });
    row.append(head, fields);
    return row;
  }
  form.addEventListener("click", (event) => {
    const add = event.target.closest("[data-add-line]");
    if (add) {
      const kind = add.dataset.addLine;
      const row = makeRow(kind);
      groups[kind].append(row);
      refresh(kind);
      row.querySelector("input").focus();
      status.textContent = `${kind === "quote" ? "Quote" : "Rate-card"} item added.`;
    }
    const remove = event.target.closest("[data-remove-line]");
    if (remove) {
      const group = remove.closest("[data-lines]");
      const kind = group.dataset.lines;
      if (kind === "quote" && group.children.length <= 1) return;
      remove.closest(".project-line").remove();
      refresh(kind);
      form.querySelector(`[data-add-line="${kind}"]`).focus();
      status.textContent = "Item removed.";
    }
  });
  const text = document.getElementById("chat-text");
  const file = document.getElementById("chat-file");
  function validateChat() {
    const hasText = text.value.trim().length > 0;
    const upload = file.files[0];
    let message = "";
    if (!hasText && !upload) message = "Paste a WhatsApp export or upload a .txt file.";
    else if (hasText && upload) message = "Use one input only: clear the pasted text or remove the selected file.";
    else if (upload && !upload.name.toLowerCase().endsWith(".txt")) message = "Choose a UTF-8 .txt export without media.";
    else if (new Blob([text.value]).size + (upload ? upload.size : 0) >= 1000000) message = "Keep the conversation under 1 MB total.";
    text.setCustomValidity(message);
  }
  text.addEventListener("input", validateChat);
  file.addEventListener("change", validateChat);
  form.addEventListener("submit", (event) => {
    validateChat();
    if (!form.reportValidity()) event.preventDefault();
  });
  refresh("quote");
  refresh("extra");
  document.getElementById("project-errors")?.focus();
})();
