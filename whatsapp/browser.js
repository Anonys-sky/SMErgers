'use strict';

const fs = require('node:fs');
const path = require('node:path');

function executablePath(env = process.env) {
    const configured = (env.PUPPETEER_EXECUTABLE_PATH || '').trim();
    if (configured) return configured;
    for (const directory of (env.PATH || '').split(path.delimiter).filter(Boolean)) {
        for (const name of ['chromium', 'chromium-browser', 'google-chrome']) {
            const candidate = path.resolve(directory, name);
            try {
                fs.accessSync(candidate, fs.constants.X_OK);
                if (fs.statSync(candidate).isFile()) return candidate;
            } catch {
                // Keep searching PATH; Puppeteer may supply its own browser locally.
            }
        }
    }
    return undefined;
}

function browserOptions(env = process.env) {
    return {
        executablePath: executablePath(env),
        headless: (env.WHATSAPP_HEADLESS || 'true').toLowerCase() !== 'false',
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--disable-gpu',
        ],
    };
}

async function checkBrowser() {
    const { createRequire } = require('node:module');
    const bridgeRequire = createRequire(require.resolve('whatsapp-web.js'));
    const puppeteer = bridgeRequire('puppeteer');
    const browser = await puppeteer.launch({ ...browserOptions(), headless: true, timeout: 30000 });
    try {
        const page = await browser.newPage();
        await page.setContent('<title>Bridge browser check</title>');
        if (await page.title() !== 'Bridge browser check') {
            throw new Error('Browser could not render the test page.');
        }
        console.log(`[whatsapp] Browser check passed: ${await browser.version()}`);
    } finally {
        await browser.close();
    }
}

module.exports = { executablePath, browserOptions };

if (require.main === module) {
    checkBrowser().catch((err) => {
        console.error(`[whatsapp] Browser check failed: ${err.message}`);
        process.exitCode = 1;
    });
}
