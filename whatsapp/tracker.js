'use strict';

const { toRecord, messageId, contactName } = require('./convert');

// Keep every message seen after a group is selected, even when it falls outside
// the history window before Flask next polls. State lasts for this bridge process.
class GroupTracker {
    constructor() {
        this.groups = new Map();
    }

    watch(groupId) {
        if (!this.groups.has(groupId)) this.groups.set(groupId, new Map());
    }

    capture(msg, me) {
        const groupId = msg.id?.remote?._serialized || msg.id?.remote || (msg.fromMe ? msg.to : msg.from);
        const records = this.groups.get(groupId);
        if (!records) return;
        const sender = msg.fromMe ? (me?.name || 'Me')
            : (msg._data?.notifyName || contactName(null, msg.author || msg.from));
        const record = toRecord(msg, sender);
        if (record) records.set(record.wa_id, record);
    }

    merge(groupId, history) {
        this.watch(groupId);
        const records = this.groups.get(groupId);
        for (const record of history) {
            const id = messageId(record.wa_id);
            if (id && !records.has(id)) records.set(id, { ...record, wa_id: id });
        }
        return [...records.values()].sort((a, b) => a.timestamp - b.timestamp);
    }
}

module.exports = { GroupTracker };
