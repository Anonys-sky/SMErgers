'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { executablePath, browserOptions } = require('./browser');

test('an explicit browser executable takes precedence over PATH', () => {
    assert.equal(executablePath({
        PUPPETEER_EXECUTABLE_PATH: ' /custom/chrome ',
        PATH: '/usr/bin',
    }), '/custom/chrome');
});

test('the bridge finds an executable system Chromium and skips non-executable files', (t) => {
    const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'bridge-browser-'));
    t.after(() => fs.rmSync(directory, { recursive: true, force: true }));
    const chromium = path.join(directory, 'chromium');
    const chrome = path.join(directory, 'google-chrome');
    fs.writeFileSync(chromium, 'not executable', { mode: 0o644 });
    fs.writeFileSync(chrome, '#!/bin/sh\n', { mode: 0o755 });
    assert.equal(executablePath({ PATH: directory }), chrome);
    fs.chmodSync(chromium, 0o755);
    assert.equal(executablePath({ PATH: directory }), chromium);
});

test('local installations without a system browser can use Puppeteer defaults', () => {
    assert.equal(executablePath({ PATH: '' }), undefined);
    assert.equal(browserOptions({ PATH: '' }).headless, true);
    assert.equal(browserOptions({ PATH: '', WHATSAPP_HEADLESS: 'FALSE' }).headless, false);
});
