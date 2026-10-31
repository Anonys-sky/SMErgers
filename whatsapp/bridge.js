'use strict';
/**
 * WhatsApp bridge: keeps one WhatsApp Web session (your WhatsApp account as a linked
 * device) and lets the SMErgers web app read group messages directly, without an exported .txt.
 *
 *   node whatsapp/bridge.js        (or: npm run whatsapp)
 *
 * Two pairing options:
 *   1. Scan QR code (auto-refreshed, rendered on the app's /whatsapp page)
 *   2. Enter phone number to get an 8-character pairing code directly on your phone
 *
 * Session is stored in whatsapp/.wwebjs_auth so it stays linked across restarts.
 *
 * Local HTTP API, bound to 127.0.0.1 only:
 *   GET /status                                connection state, live QR code, loading info
 *   POST /pair (body { phone }) OR GET /pair?phone=... request 8-digit phone pairing code
 *   GET /groups                                groups this number is in
 *   GET /groups/<group id>/messages?limit=N    latest N messages of one group
 */
const http = require('http');
const path = require('path');
const QRCode = require('qrcode');
const { Client, LocalAuth } = require('whatsapp-web.js');
const { toRecord, contactName } = require('./convert');
const { browserOptions } = require('./browser');
const { browserSessionLost } = require('./recovery');
const { GroupTracker } = require('./tracker');
const tracker = new GroupTracker();

const PORT = Number(process.env.WHATSAPP_BRIDGE_PORT || 3001);
const DEFAULT_LIMIT = 2000;
const MAX_LIMIT = 20000;
const RESTART_DELAY_MS = 5000;
const QR_REFRESH_INTERVAL_MS = 20000;

const ALLOWED_HOSTS = new Set([`127.0.0.1:${PORT}`, `localhost:${PORT}`]);

const state = {
    status: 'starting', // starting | qr | authenticated | ready | logged_out | disconnected | error
    qr: null,           // data: URL of the current QR code, only while status is "qr"
    pairing_code: null, // 8-character code if requested via phone number
    loading: null,      // WhatsApp Web loading progress { percent, message }
    me: null,           // { name, number } once ready
    error: null,
    since: new Date().toISOString(),
};

let client = null;
let restartTimer = null;
let qrRefreshTimer = null;

function setStatus(status, extra = {}) {
    Object.assign(state, { status, error: null, since: new Date().toISOString() }, extra);
    if (status !== 'qr') state.qr = null;
    console.log(`[whatsapp] ${status}${state.error ? `: ${state.error}` : ''}`);
}

function scheduleRestart(reason) {
    if (restartTimer) return;
    console.log(`[whatsapp] restarting in ${RESTART_DELAY_MS / 1000}s (${reason})`);
    restartTimer = setTimeout(async () => {
        restartTimer = null;
        const old = client;
        client = null;
        if (old) {
            try { await old.destroy(); } catch (ignored) { /* already closed */ }
        }
        start();
    }, RESTART_DELAY_MS);
}

function start() {
    setStatus('starting', { me: null, loading: null, pairing_code: null });
    if (qrRefreshTimer) clearInterval(qrRefreshTimer);

    client = new Client({
        authStrategy: new LocalAuth({ dataPath: path.join(__dirname, '.wwebjs_auth') }),
        webVersionCache: { type: 'none' },
        userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
        puppeteer: browserOptions(),
    });
    const currentClient = client;

    // message_create includes messages sent by the linked account as well as
    // incoming messages. The 'message' event excludes our own messages.
    client.on('message_create', (msg) => tracker.capture(msg, state.me));

    client.on('qr', async (qr) => {
        try {
            const dataUrl = await QRCode.toDataURL(qr, { margin: 2, width: 300 });
            setStatus('qr', { qr: dataUrl });
            console.log('[whatsapp] Scan the QR code or link using a phone number on the app /whatsapp page.');
        } catch (err) {
            setStatus('error', { error: `Could not draw the QR code: ${err.message}` });
        }
    });

    client.on('code', (code) => {
        console.log('[whatsapp] Pairing code ready on the app /whatsapp page.');
        state.pairing_code = code;
    });

    client.on('loading_screen', (percent, message) => {
        console.log(`[whatsapp] loading: ${percent}% (${message})`);
        state.loading = { percent, message };
    });

    client.on('authenticated', () => {
        setStatus('authenticated');
        state.pairing_code = null;
    });

    client.on('auth_failure', (message) => {
        setStatus('error', { error: `Login failed: ${message}. Cleared session, please scan again.` });
    });

    client.on('ready', () => {
        const info = client.info || {};
        setStatus('ready', {
            loading: null,
            pairing_code: null,
            me: { name: info.pushname || null, number: info.wid ? info.wid.user : null },
        });
        currentClient.pupPage?.once('close', () => {
            if (stopping || client !== currentClient || state.status === 'logged_out') return;
            setStatus('error', { error: 'WhatsApp Web browser page closed.' });
            scheduleRestart('browser page closed');
        });
    });

    client.on('disconnected', (reason) => {
        if (reason === 'LOGOUT') {
            setStatus('logged_out', { me: null, pairing_code: null });
            return;
        }
        setStatus('disconnected', { me: null, pairing_code: null, error: String(reason) });
        scheduleRestart(`disconnected: ${reason}`);
    });

    // Keep the QR code fresh: trigger WhatsApp Web's refreshQR if it goes idle on QR screen
    qrRefreshTimer = setInterval(async () => {
        if (state.status === 'qr' && client && client.pupPage) {
            try {
                await client.pupPage.evaluate(() => {
                    const Cmd = window.require && window.require('WAWebCmd');
                    if (Cmd && Cmd.Cmd && typeof Cmd.Cmd.refreshQR === 'function') {
                        Cmd.Cmd.refreshQR();
                    }
                });
            } catch (ignored) {}
        }
    }, QR_REFRESH_INTERVAL_MS);

    client.initialize().catch((err) => {
        setStatus('error', { error: `WhatsApp Web did not start: ${err.message}` });
        scheduleRestart('start-up failed');
    });
}

let queue = Promise.resolve();
function serial(task) {
    const run = queue.then(task, task);
    queue = run.catch(() => {});
    return run;
}

async function senderName(msg, cache) {
    if (msg.fromMe) return (state.me && state.me.name) || 'Me';
    const id = msg.author || msg.from;
    if (!cache.has(id)) {
        let contact = null;
        try { contact = await client.getContactById(id); } catch (ignored) { /* unknown contact */ }
        const notify = msg._data && msg._data.notifyName;
        cache.set(id, contact ? contactName(contact, id) : (notify || contactName(null, id)));
    }
    return cache.get(id);
}

function participantCount(chat) {
    const meta = chat.groupMetadata;
    return meta && Array.isArray(meta.participants) ? meta.participants.length : null;
}

async function listGroups() {
    return await client.pupPage.evaluate(() => {
        try {
            const ChatCollection = window.require('WAWebCollections').Chat;
            const chats = ChatCollection.getModelsArray();
            return chats
                .filter((c) => c.isGroup || (c.id && c.id._serialized && c.id._serialized.endsWith('@g.us')))
                .map((c) => {
                    let participants = null;
                    try {
                        if (c.groupMetadata && c.groupMetadata.participants) {
                            participants = c.groupMetadata.participants.length;
                        }
                    } catch (e) {}
                    return {
                        id: c.id._serialized,
                        name: c.formattedTitle || c.name || c.contact?.name || 'Group',
                        participants,
                        last_message_at: c.t || null,
                        archived: Boolean(c.archive),
                    };
                })
                .sort((a, b) => (b.last_message_at || 0) - (a.last_message_at || 0));
        } catch (err) {
            console.error('Error listing groups:', err);
            return [];
        }
    });
}

async function groupMessages(groupId, limit) {
    const result = await client.pupPage.evaluate(async (groupId, limit) => {
        try {
            const chatWid = window.require('WAWebWidFactory').createWid(groupId);
            const ChatCollection = window.require('WAWebCollections').Chat;
            let chat = ChatCollection.get(chatWid);
            if (!chat) {
                const findAction = window.require('WAWebFindChatAction');
                if (findAction && findAction.findOrCreateLatestChat) {
                    chat = (await findAction.findOrCreateLatestChat(chatWid))?.chat;
                }
            }
            if (!chat) return null;

            // Load earlier messages if requested
            let msgs = chat.msgs ? chat.msgs.getModelsArray().filter((m) => !m.isNotification) : [];
            if (limit > msgs.length) {
                try {
                    const loader = window.require('WAWebChatLoadMessages');
                    while (msgs.length < limit) {
                        const loaded = await loader.loadEarlierMsgs({ chat });
                        if (!loaded || !loaded.length) break;
                        msgs = [...loaded.filter((m) => !m.isNotification), ...msgs];
                    }
                } catch (e) {}
            }
            if (msgs.length > limit) {
                msgs.sort((a, b) => ((a.t || 0) > (b.t || 0) ? 1 : -1));
                msgs = msgs.splice(msgs.length - limit);
            }
            msgs.sort((a, b) => (a.t || 0) - (b.t || 0));

            const records = [];
            for (const m of msgs) {
                records.push({
                    id: { _serialized: m.id?._serialized, id: m.id?.id,
                        remote: m.id?.remote?._serialized || m.id?.remote,
                        fromMe: Boolean(m.id?.fromMe) },
                    timestamp: Number(m.t), type: m.type,
                    body: typeof m.body === 'string' ? m.body : (m.caption || ''),
                    hasMedia: Boolean(m.directPath), fromMe: Boolean(m.id?.fromMe),
                    isStatus: Boolean(m.isStatus),
                    author: m.author?._serialized || m.author,
                    from: m.from?._serialized || m.from,
                    _data: { notifyName: m.notifyName },
                });
            }
            return {
                group: { id: chat.id._serialized, name: chat.formattedTitle || chat.name || 'Group' },
                limit,
                fetched: msgs.length,
                skipped: 0,
                messages: records,
            };
        } catch (err) {
            console.error('Error in groupMessages evaluate:', err);
            return null;
        }
    }, groupId, limit);
    if (!result) return null;
    // History and live events must share the exact conversion and identity rules.
    result.messages = result.messages.map(msg => toRecord(msg, msg.fromMe
        ? (state.me?.name || 'Me')
        : (msg._data?.notifyName || contactName(null, msg.author || msg.from))))
        .filter(Boolean);
    return result;
}

function send(res, code, body) {
    const json = JSON.stringify(body);
    res.writeHead(code, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' });
    res.end(json);
}

function parseLimit(raw) {
    if (raw === null || raw === '') return DEFAULT_LIMIT;
    const n = Number(raw);
    if (!Number.isInteger(n) || n < 1) return null;
    return Math.min(n, MAX_LIMIT);
}

const server = http.createServer(async (req, res) => {
    if (!ALLOWED_HOSTS.has(req.headers.host || '')) return send(res, 403, { error: 'Forbidden host' });
    const url = new URL(req.url, `http://${req.headers.host}`);

    if (req.method === 'GET' && url.pathname === '/status') {
        return send(res, 200, state);
    }

    // Request pairing code via phone number
    if (url.pathname === '/pair') {
        let phone = url.searchParams.get('phone');
        if (req.method === 'POST') {
            const body = await new Promise((resolve) => {
                let data = '';
                req.on('data', chunk => { data += chunk; });
                req.on('end', () => resolve(data));
            });
            try {
                const parsed = JSON.parse(body);
                if (parsed.phone) phone = parsed.phone;
            } catch (e) {}
        }
        if (!phone) return send(res, 400, { error: 'phone number is required' });
        const cleanPhone = String(phone).replace(/\D/g, '');
        if (cleanPhone.length < 8) return send(res, 400, { error: 'valid country code and phone number required' });

        if (!client || !client.pupPage) {
            return send(res, 503, { error: 'WhatsApp Web is not ready yet' });
        }
        try {
            console.log('[whatsapp] Requesting a pairing code.');
            const code = await client.requestPairingCode(cleanPhone);
            state.pairing_code = code;
            return send(res, 200, { code, phone: cleanPhone });
        } catch (err) {
            console.error('[whatsapp] Pairing code error:', err.message);
            recoverBrowserSession(err);
            return send(res, 500, { error: err.message || 'Could not request pairing code' });
        }
    }

    if (req.method !== 'GET') return send(res, 405, { error: 'GET requests only' });

    const ready = state.status === 'ready' && client;
    try {
        if (url.pathname === '/groups') {
            if (!ready) return send(res, 503, { error: 'WhatsApp is not connected yet', status: state.status });
            return send(res, 200, { groups: await serial(listGroups) });
        }
        const match = url.pathname.match(/^\/groups\/([^/]+)\/messages$/);
        if (match) {
            if (!ready) return send(res, 503, { error: 'WhatsApp is not connected yet', status: state.status });
            const groupId = decodeURIComponent(match[1]);
            if (!groupId.endsWith('@g.us')) return send(res, 400, { error: 'Not a group id' });
            const limit = parseLimit(url.searchParams.get('limit'));
            if (limit === null) return send(res, 400, { error: 'limit must be a whole number above 0' });
            tracker.watch(groupId); // subscribe before the history read to avoid a gap
            const result = await serial(() => groupMessages(groupId, limit));
            if (!result) return send(res, 404, { error: 'Group not found on this WhatsApp number' });
            result.messages = tracker.merge(groupId, result.messages);
            result.fetched = result.messages.length;
            return send(res, 200, result);
        }
        return send(res, 404, { error: 'Not found' });
    } catch (err) {
        console.error('[whatsapp] request failed:', err);
        recoverBrowserSession(err);
        return send(res, 500, { error: err.message || 'WhatsApp request failed' });
    }
});

function recoverBrowserSession(err) {
    if (!browserSessionLost(err) || restartTimer || stopping) return;
    setStatus('error', { error: `WhatsApp Web browser session was lost: ${err.message}` });
    scheduleRestart('browser session lost');
}

server.on('error', (err) => {
    console.error(`[whatsapp] cannot listen on 127.0.0.1:${PORT}: ${err.message}`);
    process.exit(1);
});

server.listen(PORT, '127.0.0.1', () => {
    console.log(`[whatsapp] bridge listening on http://127.0.0.1:${PORT}`);
    start();
});

let stopping = false;
async function shutdown(signal) {
    if (stopping) return;
    stopping = true;
    console.log(`[whatsapp] ${signal}: closing WhatsApp Web`);
    if (restartTimer) clearTimeout(restartTimer);
    if (qrRefreshTimer) clearInterval(qrRefreshTimer);
    server.close();
    try { if (client) await client.destroy(); } catch (ignored) { /* already closed */ }
    process.exit(0);
}
process.on('SIGINT', () => shutdown('SIGINT'));
process.on('SIGTERM', () => shutdown('SIGTERM'));

// whatsapp-web.js re-injects its page hooks inside async event handlers (for example after a
// logout redirect). If that fails the rejection is unhandled and would kill the whole bridge,
// so log it and restart the WhatsApp client instead.
process.on('unhandledRejection', (reason) => {
    const message = reason && reason.message ? reason.message : String(reason);
    console.error(`[whatsapp] unhandled error: ${message}`);
    if (stopping) return;
    setStatus('error', { error: message });
    scheduleRestart('unhandled error');
});
