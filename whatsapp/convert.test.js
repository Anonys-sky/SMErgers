'use strict';
// Run with: npm test   (Node's built-in test runner, no extra packages)
const test = require('node:test');
const assert = require('node:assert/strict');
const { toRecord, contactName, MEDIA_PLACEHOLDER, DELETED_TEXT } = require('./convert');

function msg(fields) {
    return {
        id: { _serialized: 'false_120363000000000000@g.us_3EB0ABC' },
        timestamp: 1789460700,
        type: 'chat',
        body: '',
        hasMedia: false,
        fromMe: false,
        isStatus: false,
        ...fields,
    };
}

test('text message keeps body, sender and time', () => {
    const r = toRecord(msg({ body: '  ok go ahead  ' }), 'Mr Tan');
    assert.deepEqual(r, {
        wa_id: 'false_120363000000000000@g.us_3EB0ABC',
        timestamp: 1789460700,
        sender: 'Mr Tan',
        text: 'ok go ahead',
        is_media: false,
        from_me: false,
    });
});

test('multi-line text stays one record', () => {
    const r = toRecord(msg({ body: 'Recap:\n- 195 pax\n- 3 banners' }), 'Aisyah');
    assert.equal(r.text, 'Recap:\n- 195 pax\n- 3 banners');
});

test('media without caption becomes the export placeholder', () => {
    const r = toRecord(msg({ type: 'image', hasMedia: true, body: '' }), 'Aisyah');
    assert.equal(r.text, MEDIA_PLACEHOLDER);
    assert.equal(r.is_media, true);
});

test('media caption is kept as readable text', () => {
    const r = toRecord(msg({ type: 'image', hasMedia: true, body: 'LED upgrade RM 1,100 more' }), 'Aisyah');
    assert.equal(r.text, 'LED upgrade RM 1,100 more');
    assert.equal(r.is_media, false);
});

test('voice note without download path is still media', () => {
    const r = toRecord(msg({ type: 'ptt', hasMedia: false, body: '' }), 'Linda');
    assert.equal(r.is_media, true);
});

test('deleted message reads like the export', () => {
    assert.equal(toRecord(msg({ type: 'revoked' }), 'Linda').text, DELETED_TEXT);
});

test('notifications, reactions and undecrypted messages are skipped', () => {
    for (const type of ['gp2', 'e2e_notification', 'notification_template', 'reaction', 'protocol', 'ciphertext', 'call_log']) {
        assert.equal(toRecord(msg({ type, body: 'x' }), 'A'), null, type);
    }
    assert.equal(toRecord(msg({ isStatus: true, body: 'status' }), 'A'), null);
    assert.equal(toRecord(msg({ body: '   ' }), 'A'), null);
});

test('own messages are marked from_me', () => {
    assert.equal(toRecord(msg({ body: 'noted', fromMe: true }), 'Fiesta Events').from_me, true);
});

test('contact name prefers the saved name, then business and push names, then number', () => {
    assert.equal(contactName({ name: 'Mr Tan (Sinar)', pushname: 'Tan' }, 'x@c.us'), 'Mr Tan (Sinar)');
    assert.equal(contactName({ verifiedName: 'Sinar Trading', pushname: 'Tan' }, 'x@c.us'), 'Sinar Trading');
    assert.equal(contactName({ pushname: 'Tan' }, 'x@c.us'), 'Tan');
    assert.equal(contactName({ number: '60123456789' }, 'x@c.us'), '+60123456789');
    assert.equal(contactName(null, '60198765432@c.us'), '+60198765432');
    assert.equal(contactName(null, ''), 'Unknown');
});
