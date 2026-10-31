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
