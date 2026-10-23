const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

test("workspace tables combine keyword and state filters and recover from empty results", () => {
  const search = { value: "", addEventListener(event, fn) { this[event] = fn; } };
  const state = { value: "", addEventListener(event, fn) { this[event] = fn; } };
  const empty = { hidden: true, setAttribute() {} };
  const rows = [
    { textContent: "Annual Dinner LED wall upgrade", dataset: { state: "reviewed" } },
    { textContent: "Annual Dinner Wireless mic", dataset: { state: "detected" } },
    { textContent: "Product Launch LED wall", dataset: { state: "reviewed" } },
  ];
  const region = {
    querySelector(selector) {
      return { "[data-search]": search, "[data-state-filter]": state, "[data-filter-empty]": empty }[selector];
    },
    querySelectorAll() { return rows; },
  };
  const document = { querySelectorAll() { return [region]; } };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, "../src/static/workspace.js"), "utf8"), { document });

  search.value = " annual dinner ";
  search.input();
  assert.deepEqual(rows.map(row => row.hidden), [false, false, true]);
  state.value = "reviewed";
  state.change();
  assert.deepEqual(rows.map(row => row.hidden), [false, true, true]);
  search.value = "nonexistent";
  search.input();
  assert.ok(empty.hidden === false && rows.every(row => row.hidden));
  search.value = "";
  state.value = "";
  state.change();
  assert.ok(empty.hidden === true && rows.every(row => !row.hidden));
});
