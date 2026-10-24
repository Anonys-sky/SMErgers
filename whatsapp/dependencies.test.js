'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { createRequire } = require('node:module');
const lock = require('../package-lock.json');

test('browser dependency tree excludes the vulnerable ZIP and FTP packages', () => {
    for (const name of Object.keys(lock.packages)) {
        assert.ok(!name.endsWith('/extract-zip'), `${name} has no patched release`);
        assert.ok(!name.endsWith('/basic-ftp'), `${name} should no longer be needed`);
    }
});

test('every locked Zod copy includes the resource-exhaustion fix', () => {
    const entries = Object.entries(lock.packages).filter(([name]) => name.endsWith('/zod'));
    assert.ok(entries.length > 0, 'expected the browser protocol validator');
    for (const [name, { version }] of entries) {
        const [major, minor, patch] = version.split('.').map(Number);
        assert.ok(
            major > 4 || (major === 4 && (minor > 6 || (minor === 6 && patch >= 6))),
            `${name}@${version} must be at least 4.6.6`,
        );
    }
});

test('WhatsApp can load the upgraded Puppeteer from CommonJS', () => {
    const { Client, LocalAuth } = require('whatsapp-web.js');
    const bridgeRequire = createRequire(require.resolve('whatsapp-web.js'));
    const puppeteer = bridgeRequire('puppeteer');
    assert.equal(typeof puppeteer.launch, 'function');
    assert.equal(typeof puppeteer.connect, 'function');
    const client = new Client({ authStrategy: new LocalAuth() });
    assert.ok(client instanceof Client);
    // No initialization: this check must not pair an account or create a session.
});
