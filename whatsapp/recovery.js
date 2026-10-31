'use strict';

function browserSessionLost(error) {
    const message = error?.message || String(error);
    return /detached Frame|frame was detached|Execution context was destroyed|Target closed|Session closed/i.test(message);
}

module.exports = { browserSessionLost };
