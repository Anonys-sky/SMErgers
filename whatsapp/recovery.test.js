'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { browserSessionLost } = require('./recovery');

test('detects browser failures that need a fresh WhatsApp client', () => {
    for (const message of [
        "Attempted to use detached Frame 'abc'.",
        'Execution context was destroyed, most likely because of a navigation.',
        'Protocol error (Runtime.callFunctionOn): Target closed',
        'Session closed. Most likely the page has been closed.',
    ]) {
        assert.equal(browserSessionLost(new Error(message)), true, message);
    }
    assert.equal(browserSessionLost(new Error('Group not found')), false);
});
