// MacroMatch food picker: all filtering happens in the browser.
// No server calls, external libraries, HTML injection or backend identity guesses.
export function normalizeSearch(value) {
  return String(value ?? "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim();
}

export function matchesFood(item, query) {
  const words = normalizeSearch(query).split(/\s+/).filter(Boolean);
  const searchable = normalizeSearch(
    String(item.name ?? "") + " " +
    String(item.source ?? "") + " " +
    String(item.fdc_id ?? "")
  );
  return words.every((word) => searchable.includes(word));
}

export default function (component) {
  const { parentElement, data, setStateValue } = component;
  const root = parentElement.querySelector(".mm-picker");
  const field = root.querySelector(".mm-picker-input");
  const label = root.querySelector(".mm-picker-label");
  const results = root.querySelector(".mm-picker-results");
  const clearButton = root.querySelector(".mm-picker-clear");
  const status = root.querySelector(".mm-picker-status");
  const options = Array.isArray(data?.options) ? data.options : [];
  const byKey = new Map(options.map((item) => [item.key, item]));
  let selected = byKey.has(data?.selection) ? data.selection : null;
  let visible = [];
  let active = 0;
  let open = false;

  // The HTML is trusted static markup. USDA names are inserted only as text.
  label.textContent = String(data?.label ?? "Choose a food");
  field.setAttribute("aria-label", label.textContent);
  field.placeholder = "Search foods...";
  if (selected !== null) {
    const current = byKey.get(selected);
    if (field.value !== current.name) field.value = current.name;
  }

  function close() {
    open = false;
    results.hidden = true;
    field.setAttribute("aria-expanded", "false");
    field.removeAttribute("aria-activedescendant");
  }

  function highlight() {
    const items = Array.from(results.querySelectorAll('[role="option"]'));
    items.forEach((button, index) => {
      const focused = index === active;
      button.setAttribute("aria-selected", String(focused));
      button.classList.toggle("is-active", focused);
      if (focused) field.setAttribute("aria-activedescendant", button.id);
    });
    if (items[active]) items[active].scrollIntoView({ block: "nearest" });
  }

  function choose(item) {
    selected = item.key;
    field.value = item.name;
    close();
    setStateValue("selection", item.key);
  }

  function showMatches() {
    visible = options.filter((item) => matchesFood(item, field.value));
    active = 0;
    results.replaceChildren();
    const list = document.createElement("div");
    list.className = "mm-picker-options";
    list.setAttribute("role", "listbox");
    list.id = "mm-picker-listbox";
    visible.forEach((item, index) => {
      const button = document.createElement("button");
      button.type = "button";
      button.id = "mm-picker-option-" + index;
      button.className = "mm-picker-option";
      button.setAttribute("role", "option");
      button.setAttribute("aria-selected", "false");
      button.tabIndex = -1;
      const title = document.createElement("span");
      title.className = "mm-picker-name";
      title.textContent = item.name;
      const meta = document.createElement("span");
      meta.className = "mm-picker-meta";
      meta.textContent = item.source + "  ·  FDC " + item.fdc_id;
      button.append(title, meta);
      button.addEventListener("pointerdown", (event) => event.preventDefault());
      button.addEventListener("click", () => choose(item));
      list.appendChild(button);
    });
    if (visible.length === 0) {
      const empty = document.createElement("div");
      empty.className = "mm-picker-empty";
      empty.textContent = "No matching foods. Try different words.";
      list.appendChild(empty);
    }
    status.textContent = visible.length + " matching foods";
    results.append(status, list);
    open = true;
    results.hidden = false;
    field.setAttribute("aria-expanded", "true");
    highlight();
  }

  const onFocus = () => {
    if (selected !== null) field.select();
    showMatches();
  };
  const onInput = () => {
    // Once a user edits a committed selection, it is no longer selected.
    // This runs only on the first edit, so subsequent keystrokes stay local.
    if (selected !== null && field.value !== byKey.get(selected).name) {
      selected = null;
      setStateValue("selection", null);
    }
    showMatches();
  };
  const onKeydown = (event) => {
    if (event.key === "Escape") {
      close();
    } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (!open) showMatches();
      else if (visible.length) {
        active = (active + (event.key === "ArrowDown" ? 1 : -1) + visible.length) % visible.length;
        highlight();
      }
    } else if (event.key === "Enter" && open && visible[active]) {
      event.preventDefault();
      choose(visible[active]);
    } else if (event.key === "Tab") {
      close();
    }
  };
  const onClear = () => {
    field.value = "";
    if (selected !== null) {
      selected = null;
      setStateValue("selection", null);
    }
    field.focus();
    showMatches();
  };
  const onOutsidePointer = (event) => {
    if (!event.composedPath().includes(root)) close();
  };

  field.addEventListener("focus", onFocus);
  field.addEventListener("input", onInput);
  field.addEventListener("keydown", onKeydown);
  clearButton.addEventListener("click", onClear);
  document.addEventListener("pointerdown", onOutsidePointer);
  // Keep the live suggestion list open if the first edited character caused
  // a Python rerun to clear the previously committed selection.
  if (parentElement.activeElement === field && field.value) showMatches();
  return () => {
    field.removeEventListener("focus", onFocus);
    field.removeEventListener("input", onInput);
    field.removeEventListener("keydown", onKeydown);
    clearButton.removeEventListener("click", onClear);
    document.removeEventListener("pointerdown", onOutsidePointer);
  };
}
