'use strict';
/**
 * Turns whatsapp-web.js Message objects into the plain records the Python app reads.
 * Kept free of any WhatsApp connection so it can be tested on its own (convert.test.js).
 *
 * Record shape (one per message, oldest first):
 *   { wa_id, timestamp, sender, text, is_media, from_me }
 */

// Protocol and housekeeping events: never shown as messages in a WhatsApp export either.
const SKIP_TYPES = new Set([
    'protocol', 'reaction', 'e2e_notification', 'gp2', 'group_notification', 'notification',
    'notification_template', 'call_log', 'debug', 'broadcast_notification', 'ciphertext',
]);

// Types whose content is an attachment; the caption, if any, is the text worth reading.
const MEDIA_TYPES = new Set(['image', 'video', 'audio', 'ptt', 'document', 'sticker', 'album']);

// Same placeholder a "Without media" export uses, so the Python side treats both sources alike.
const MEDIA_PLACEHOLDER = '<Media omitted>';
const DELETED_TEXT = 'This message was deleted';

function messageId(id) {
    // Live events can carry a plain MsgKey without _serialized. Never stringify
    // that object: it becomes "[object Object]" for every live message.
    let serialized = typeof id === 'string' ? id : id?._serialized;
    if (!serialized && id?.id && id?.remote) {
        const remote = id.remote._serialized || id.remote;
        serialized = `${Boolean(id.fromMe)}_${remote}_${id.id}`;
    }
    if (!serialized || serialized === '[object Object]' || typeof serialized !== 'string') return null;
    // The participant suffix can change between phone and LID addressing.
    // Group + WhatsApp stanza ID + direction identify the same message in both paths.
    const match = serialized.match(/^(true|false)_([^_]+)_([^_]+)(?:_.*)?$/);
    return match ? `${match[1]}_${match[2]}_${match[3]}` : serialized;
}

/**
 * @param {object} msg       whatsapp-web.js Message
 * @param {string} sender    display name already resolved for this message
 * @returns {object|null}    record, or null if the message carries nothing to read
 */
function toRecord(msg, sender) {
    if (!msg || msg.isStatus || SKIP_TYPES.has(msg.type)) return null;
    const waId = messageId(msg.id);
    if (!waId || !Number.isFinite(Number(msg.timestamp))) return null;
    const body = typeof msg.body === 'string' ? msg.body.trim() : '';
    let text = body;
    let isMedia = false;
    if (msg.type === 'revoked') {
        text = DELETED_TEXT;
    } else if (msg.hasMedia || MEDIA_TYPES.has(msg.type)) {
        // A caption such as "ok go ahead" under a photo is still an agreement, so keep it as text.
        if (!body) {
            text = MEDIA_PLACEHOLDER;
            isMedia = true;
        }
    } else if (!body) {
        return null;
    }
    return {
        wa_id: waId,
        timestamp: Number(msg.timestamp),
        sender,
        text,
        is_media: isMedia,
        from_me: Boolean(msg.fromMe),
    };
}

/** Best display name for a contact, closest to what an exported chat would show. */
function contactName(contact, fallbackId) {
    if (contact) {
        const name = contact.name || contact.verifiedName || contact.pushname || contact.shortName;
        if (name) return name;
        if (contact.number) return `+${contact.number}`;
    }
    const user = String(fallbackId || '').split('@')[0];
    return user ? `+${user}` : 'Unknown';
}

module.exports = { toRecord, messageId, contactName, SKIP_TYPES, MEDIA_TYPES, MEDIA_PLACEHOLDER, DELETED_TEXT };
