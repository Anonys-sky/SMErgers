'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { GroupTracker } = require('./tracker');

const GROUP = '123@g.us';
function message(id, fromMe = false, group = GROUP) {
    return { id: { _serialized: id }, from: fromMe ? 'me@c.us' : group,
        to: fromMe ? group : 'me@c.us', author: '60123@c.us',
        fromMe, type: 'chat', body: id, timestamp: 100,
        _data: { notifyName: 'Client' } };
}

test('tracks incoming and own messages only in selected groups', () => {
    const tracker = new GroupTracker();
    tracker.watch(GROUP);
    tracker.capture(message('incoming'));
    tracker.capture(message('outgoing', true), {name: 'PM'});
    tracker.capture(message('private', false, 'other@c.us'));
    const records = tracker.merge(GROUP, []);
    assert.deepEqual(records.map(r => [r.text, r.sender]), [['incoming', 'Client'], ['outgoing', 'PM']]);
});

test('retains arrivals during history reads and beyond the history limit without duplicates', () => {
    const tracker = new GroupTracker();
    tracker.watch(GROUP);
    tracker.capture(message('during-read'));
    tracker.capture(message('during-read'));
    const history = {wa_id: 'old', timestamp: 1, text: 'old'};
    assert.deepEqual(tracker.merge(GROUP, [history]).map(r => r.wa_id), ['old', 'during-read']);
    for (let i = 0; i < 100; i++) tracker.capture(message('new-' + i));
    assert.equal(tracker.merge(GROUP, [history]).length, 102);
});

test('plain MsgKey live events and serialized history register the same own message once', () => {
    const tracker = new GroupTracker();
    tracker.watch(GROUP);
    const event = message('Really ah', true);
    event.id = {fromMe: true, remote: GROUP, id: 'ABC123'};
    tracker.capture(event, {name: 'Steven'});
    const history = {wa_id: `true_${GROUP}_ABC123_12345@lid`, timestamp: 100,
        sender: 'Me', text: 'Really ah', from_me: true};
    const records = tracker.merge(GROUP, [history, history]);
    assert.equal(records.length, 1);
    assert.equal(records[0].wa_id, `true_${GROUP}_ABC123`);
    assert.equal(records[0].sender, 'Steven');
    tracker.capture({...event, id: {...event.id, id: 'DEF456'}});
    assert.equal(tracker.merge(GROUP, [history]).length, 2); // two real identical messages stay separate
});

test('rejects corrupt IDs and keeps messages from separate groups isolated', () => {
    const tracker = new GroupTracker();
    tracker.watch(GROUP);
    tracker.watch('456@g.us');
    tracker.capture({...message('bad'), id: {}});
    tracker.capture({...message('one'), id: {fromMe: false, remote: GROUP, id: 'ABC'}});
    tracker.capture({...message('two', false, '456@g.us'), id: {fromMe: false, remote: '456@g.us', id: 'ABC'}});
    assert.equal(tracker.merge(GROUP, [{wa_id: '[object Object]', timestamp: 100}]).length, 1);
    assert.equal(tracker.merge('456@g.us', []).length, 1);
});
