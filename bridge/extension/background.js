// Email TUI Bridge. Answers requests from the local native host.
// It may organise mail, folders, tags and contacts and save drafts. The manifest
// grants no send permission, so Thunderbird refuses to send even if this file is changed.

const HOST_NAME = "email_tui_bridge";
const MAX_LIMIT = 50;
const SCAN_CAP = 500;
const SCAN_MS = 20000;
const BODY_CHARS = 100000;
const DEFAULT_SINCE_DAYS = 90;

// Generic job-search signals only. Personal rules belong in Thunderbird filters,
// which stay in the local profile, not in this public file.
const CAREER_NEVER = /jobalerts-noreply@linkedin\.com|@em\.linkedin\.com/i;
const CAREER_SENDERS = new RegExp(
  "(messages-noreply|inmail-hit-reply|hit-reply|invitations|jobs-noreply)@linkedin\\.com" +
    "|[@.](avature\\.net|myworkday(jobs)?\\.com|greenhouse(-mail)?\\.io|lever\\.co|icims\\.com" +
    "|smartrecruiters\\.com|jobvite\\.com|ashbyhq\\.com|roberthalf\\.com|dice\\.com)>?$" +
    "| via linkedin\\b",
  "i",
);
const CAREER_SUBJECT =
  /\b(interview|recruiter|recruiting|your application|application (received|status|update)|job opportunity|opportunity at)\b/i;
const MAX_EVENT_NAMES = 3;

let port = null;

function isCareer(m) {
  const author = m.author ?? "";
  if (CAREER_NEVER.test(author)) return false;
  return m.flagged === true || CAREER_SENDERS.test(author) || CAREER_SUBJECT.test(m.subject ?? "");
}

// Display name only, never the address, so toasts show "Robert Half", not mail ids.
function senderName(author) {
  const name = (author ?? "").replace(/<[^>]*>/, "").replace(/"/g, "").trim();
  if (name && !name.includes("@")) return name.slice(0, 60);
  const address = (author ?? "").match(/@([^>\s]+)/);
  return address ? address[1] : "Unknown sender";
}

function senderNames(messages) {
  return [...new Set(messages.map((m) => senderName(m.author)))].slice(0, MAX_EVENT_NAMES);
}

function connect() {
  if (port) return;
  port = messenger.runtime.connectNative(HOST_NAME);
  port.onMessage.addListener(onHostMessage);
  port.onDisconnect.addListener((closed) => {
    if (closed.error) console.error("Email TUI Bridge host:", closed.error.message);
    port = null;
  });
}

function str(value, name, max = 2000) {
  if (value === undefined || value === null) return undefined;
  if (typeof value !== "string" || value.length > max) {
    throw new Error(`invalid ${name}`);
  }
  return value;
}

function headerSummary(m) {
  return {
    id: m.id,
    messageId: m.headerMessageId,
    date: m.date instanceof Date ? m.date.toISOString() : m.date,
    from: m.author,
    subject: m.subject,
    read: m.read,
    flagged: m.flagged,
    tags: m.tags ?? [],
    size: m.size,
    account: m.folder?.accountId,
    folder: m.folder?.path,
  };
}

async function inboxFolders(accountId) {
  return messenger.folders.query({ accountId, specialUse: ["inbox"] });
}

async function mailAccounts() {
  const accounts = await messenger.accounts.list(false);
  return accounts.filter((a) => a.type !== "none" && a.type !== "local");
}

function findBody(part, type) {
  if (part.contentType === type && typeof part.body === "string" && !part.name) {
    return part.body;
  }
  for (const child of part.parts ?? []) {
    const found = findBody(child, type);
    if (found !== null) return found;
  }
  return null;
}

function htmlToText(html) {
  const doc = new DOMParser().parseFromString(html, "text/html");
  doc.querySelectorAll("script,style,head").forEach((el) => el.remove());
  return (doc.body?.textContent ?? "").replace(/[ \t]+/g, " ").replace(/\n{3,}/g, "\n\n").trim();
}

const HANDLERS = {
  async status() {
    const browser = await messenger.runtime.getBrowserInfo();
    const accounts = await mailAccounts();
    return {
      extension: messenger.runtime.getManifest().version,
      thunderbird: browser.version,
      accounts: accounts.length,
    };
  },

  async accounts() {
    const accounts = await mailAccounts();
    return accounts.map((a) => ({
      id: a.id,
      name: a.name,
      type: a.type,
      addresses: (a.identities ?? []).map((i) => i.email),
    }));
  },

  async unread() {
    const result = [];
    for (const account of await mailAccounts()) {
      let unread = 0;
      for (const folder of await inboxFolders(account.id)) {
        const info = await messenger.folders.getFolderInfo(folder.id);
        unread += info.unreadMessageCount ?? 0;
      }
      result.push({ account: account.id, name: account.name, unread });
    }
    return result;
  },

  // Unread inbox mail that looks job-related, per account. Counts only.
  async career() {
    const result = [];
    for (const account of await mailAccounts()) {
      const folders = await inboxFolders(account.id);
      let unread = 0;
      if (folders.length) {
        let scanned = 0;
        let page = await messenger.messages.query({
          folderId: folders.map((f) => f.id),
          read: false,
          messagesPerPage: 100,
          autoPaginationTimeout: 1000,
        });
        while (true) {
          for (const m of page.messages) {
            scanned += 1;
            if (isCareer(m)) unread += 1;
          }
          if (!page.id) break;
          if (scanned >= SCAN_CAP) {
            await messenger.messages.abortList(page.id);
            break;
          }
          page = await messenger.messages.continueList(page.id);
        }
      }
      result.push({ account: account.id, name: account.name, unread });
    }
    return result;
  },

  async search(params) {
    const limit = Math.min(Math.max(Number(params.limit) || 20, 1), MAX_LIMIT);
    const since = str(params.since, "since", 40);
    const until = str(params.until, "until", 40);
    const account = str(params.account, "account", 200);
    const query = {
      messagesPerPage: 100,
      autoPaginationTimeout: 1000,
      fromDate: since ? new Date(since) : new Date(Date.now() - DEFAULT_SINCE_DAYS * 86400000),
    };
    if (Number.isNaN(query.fromDate.getTime())) throw new Error("invalid since");
    if (until) {
      query.toDate = new Date(until);
      if (Number.isNaN(query.toDate.getTime())) throw new Error("invalid until");
    }
    if (account) query.accountId = account;
    if (params.text) query.fullText = str(params.text, "text");
    if (params.from) query.author = str(params.from, "from");
    if (params.subject) query.subject = str(params.subject, "subject");
    if (params.unread === true) query.read = false;
    if (params.flagged === true) query.flagged = true;
    const tag = str(params.tag, "tag", 100);
    if (tag) query.tags = { mode: "all", tags: { [tag]: true } };
    if (params.inboxOnly === true) {
      const accounts = account ? [{ id: account }] : await mailAccounts();
      const folders = [];
      for (const a of accounts) folders.push(...(await inboxFolders(a.id)));
      query.folderId = folders.map((f) => f.id);
    }

    const started = Date.now();
    const seen = new Map();
    let page = await messenger.messages.query(query);
    let scanned = 0;
    while (true) {
      for (const m of page.messages) {
        scanned += 1;
        // Gmail labels show the same message in several folders.
        if (!seen.has(m.headerMessageId)) seen.set(m.headerMessageId, m);
      }
      if (!page.id) break;
      if (scanned >= SCAN_CAP || Date.now() - started > SCAN_MS) {
        await messenger.messages.abortList(page.id);
        return finishSearch(seen, limit, true);
      }
      page = await messenger.messages.continueList(page.id);
    }
    return finishSearch(seen, limit, false);
  },

  async read(params) {
    const id = Number(params.id);
    if (!Number.isInteger(id)) throw new Error("invalid id");
    const header = await messenger.messages.get(id);
    const full = await messenger.messages.getFull(id);
    let body = findBody(full, "text/plain");
    if (body === null) {
      const html = findBody(full, "text/html");
      body = html === null ? "" : htmlToText(html);
    }
    const attachments = await messenger.messages.listAttachments(id);
    const extra = {};
    if (params.html === true) {
      const html = findBody(full, "text/html");
      extra.bodyHtml = html === null ? "" : html.slice(0, BODY_CHARS * 4);
    }
    return {
      ...extra,
      ...headerSummary(header),
      to: header.recipients,
      cc: header.ccList,
      attachments: attachments.map((a) => ({
        name: a.name,
        contentType: a.contentType,
        size: a.size,
      })),
      body: body.slice(0, BODY_CHARS),
      bodyTruncated: body.length > BODY_CHARS,
    };
  },

  // Opens a window for the owner to review. The extension has no send permission.
  async draft(params) {
    const tab = await messenger.compose.beginNew({
      to: str(params.to, "to"),
      cc: str(params.cc, "cc"),
      subject: str(params.subject, "subject"),
      plainTextBody: str(params.body, "body", 100000) ?? "",
      isPlainText: true,
    });
    return { opened: true, tabId: tab.id };
  },

  // Saves straight to the Drafts folder for the owner to review. Never sends.
  async saveDraft(params) {
    const details = {
      to: str(params.to, "to"),
      cc: str(params.cc, "cc"),
      bcc: str(params.bcc, "bcc"),
      subject: str(params.subject, "subject"),
      plainTextBody: str(params.body, "body", 100000) ?? "",
      isPlainText: true,
    };
    const identity = str(params.identity, "identity", 200);
    if (identity) details.identityId = identity;
    await messenger.messages.saveMessage(details, { mode: "draft" });
    return { saved: true };
  },

  // ---- Folders ----

  async folders(params) {
    const account = str(params.account, "account", 200);
    const list = await messenger.folders.query(account ? { accountId: account } : {});
    const result = [];
    for (const f of list) {
      if (f.isRoot || f.isUnified || f.isTag || f.isVirtual) continue;
      const entry = { id: f.id, account: f.accountId, path: f.path, name: f.name, specialUse: f.specialUse ?? [] };
      if (params.counts === true) {
        const info = await messenger.folders.getFolderInfo(f.id);
        entry.unread = info.unreadMessageCount ?? 0;
        entry.total = info.totalMessageCount ?? 0;
      }
      result.push(entry);
    }
    return result;
  },

  async createFolder(params) {
    const parent = await resolveFolder(params.parent, "parent");
    const created = await messenger.folders.create(parent, folderName(params.name));
    return { id: created.id, path: created.path };
  },

  async renameFolder(params) {
    const folder = await resolveFolder(params.folder);
    await refuseSpecial(folder);
    const renamed = await messenger.folders.rename(folder, folderName(params.name));
    return { id: renamed.id, path: renamed.path };
  },

  async moveFolder(params) {
    const folder = await resolveFolder(params.folder);
    await refuseSpecial(folder);
    const moved = await messenger.folders.move(folder, await resolveFolder(params.to, "to"));
    return { id: moved.id, path: moved.path };
  },

  // Only empty folders, so mail is never lost this way.
  async deleteFolder(params) {
    const folder = await resolveFolder(params.folder);
    await refuseSpecial(folder);
    const info = await messenger.folders.getFolderInfo(folder);
    const children = await messenger.folders.getSubFolders(folder, false);
    if ((info.totalMessageCount ?? 0) > 0 || children.length > 0) {
      throw new Error("folder is not empty; move its mail and subfolders out first");
    }
    await messenger.folders.delete(folder);
    return { deleted: true };
  },

  async markFolderRead(params) {
    await messenger.folders.markAsRead(await resolveFolder(params.folder));
    return { done: true };
  },

  // ---- Messages ----

  async moveMessages(params) {
    const list = messageIds(params.ids);
    await messenger.messages.move(list, await resolveFolder(params.to, "to"), { isUserAction: true });
    return { moved: list.length };
  },

  async copyMessages(params) {
    const list = messageIds(params.ids);
    await messenger.messages.copy(list, await resolveFolder(params.to, "to"), { isUserAction: true });
    return { copied: list.length };
  },

  async archiveMessages(params) {
    const list = messageIds(params.ids);
    await messenger.messages.archive(list);
    return { archived: list.length };
  },

  // Moves to each account's Trash folder. messages.delete is not used, because it
  // follows the account's deletion setting, which can remove mail permanently.
  async trashMessages(params) {
    const byAccount = new Map();
    for (const id of messageIds(params.ids)) {
      const header = await messenger.messages.get(id);
      const account = header.folder?.accountId;
      if (!account) throw new Error(`message ${id} has no account`);
      if (!byAccount.has(account)) byAccount.set(account, []);
      byAccount.get(account).push(id);
    }
    let trashed = 0;
    for (const [account, list] of byAccount) {
      const [trash] = await messenger.folders.query({ accountId: account, specialUse: ["trash"] });
      if (!trash) throw new Error(`no Trash folder in ${account}`);
      await messenger.messages.move(list, trash.id, { isUserAction: true });
      trashed += list.length;
    }
    return { trashed };
  },

  async updateMessages(params) {
    const list = messageIds(params.ids);
    const props = {};
    for (const key of ["read", "flagged", "junk"]) {
      if (params[key] === undefined) continue;
      if (typeof params[key] !== "boolean") throw new Error(`invalid ${key}`);
      props[key] = params[key];
    }
    if (params.tags !== undefined) {
      if (!Array.isArray(params.tags) || params.tags.some((t) => typeof t !== "string")) {
        throw new Error("invalid tags");
      }
      props.tags = params.tags;
    }
    if (!Object.keys(props).length) throw new Error("nothing to update");
    for (const id of list) await messenger.messages.update(id, props);
    return { updated: list.length };
  },

  // ---- Tags ----

  async tags() {
    return messenger.messages.tags.list();
  },

  async createTag(params) {
    const tag = str(params.name, "name", 100);
    const color = str(params.color, "color", 7);
    if (!tag || !/^#[0-9a-fA-F]{6}$/.test(color ?? "")) throw new Error("need name and #rrggbb color");
    const key = await messenger.messages.tags.create(str(params.key, "key", 100), tag, color);
    return { key };
  },

  async updateTag(params) {
    const props = {};
    if (params.name !== undefined) props.tag = str(params.name, "name", 100);
    if (params.color !== undefined) props.color = str(params.color, "color", 7);
    await messenger.messages.tags.update(str(params.key, "key", 100), props);
    return { updated: true };
  },

  // ---- Contacts ----

  async contacts(params) {
    const searchString = str(params.text, "text", 200);
    const found = await messenger.addressBooks.contacts.query({ searchString });
    return found.slice(0, MAX_LIMIT).map((c) => ({
      id: c.id,
      book: c.parentId,
      name: vcardValue(c.vCard, "FN"),
      emails: vcardValues(c.vCard, "EMAIL"),
    }));
  },

  async addressBooks() {
    const books = await messenger.addressBooks.list(false);
    return books.map((b) => ({ id: b.id, name: b.name, readOnly: b.readOnly ?? false }));
  },

  async createContact(params) {
    const book = str(params.book, "book", 200);
    const name = str(params.name, "name", 200);
    const email = str(params.email, "email", 320);
    if (!book || !name) throw new Error("need book and name");
    const lines = ["BEGIN:VCARD", "VERSION:4.0", `FN:${vcardEscape(name)}`];
    if (email) lines.push(`EMAIL:${vcardEscape(email)}`);
    lines.push("END:VCARD");
    const id = await messenger.addressBooks.contacts.create(book, lines.join("\r\n"));
    return { id };
  },

  async identities() {
    const result = [];
    for (const account of await mailAccounts()) {
      for (const i of await messenger.identities.list(account.id)) {
        result.push({
          id: i.id,
          account: account.id,
          accountName: account.name,
          name: i.name,
          email: i.email,
          label: i.label,
          composeHtml: i.composeHtml,
          signatureIsPlainText: i.signatureIsPlainText,
          signature: i.signature,
        });
      }
    }
    return result;
  },

  // Only the signature fields. Name, address and reply-to stay as the owner set them.
  async setSignature(params) {
    const identity = str(params.identity, "identity", 200);
    if (!identity) throw new Error("need identity");
    if (typeof params.signature !== "string" || params.signature.length > 20000) {
      throw new Error("invalid signature");
    }
    const html = params.html === true;
    const update = { signature: params.signature, signatureIsPlainText: !html };
    if (html) update.composeHtml = true;
    await messenger.identities.update(identity, update);
    return { identity, html };
  },
};

const MAX_IDS = 500;

function messageIds(value) {
  if (!Array.isArray(value) || value.length === 0 || value.length > MAX_IDS) {
    throw new Error(`ids must be a list of 1 to ${MAX_IDS} message ids`);
  }
  return value.map((v) => {
    const n = Number(v);
    if (!Number.isInteger(n)) throw new Error("invalid message id");
    return n;
  });
}

function folderName(value) {
  const name = str(value, "name", 200);
  if (!name || /[/\\]/.test(name)) throw new Error("invalid folder name");
  return name;
}

// A folder is given as its id, or as { account, path }. Path "/" is the account root.
async function resolveFolder(ref, label = "folder") {
  if (typeof ref === "string") return (await messenger.folders.get(ref)).id;
  if (ref && typeof ref === "object") {
    const accountId = str(ref.account, `${label}.account`, 200);
    const path = str(ref.path, `${label}.path`, 500);
    if (accountId && path) {
      const query = path === "/" ? { accountId, isRoot: true } : { accountId, path };
      const [found] = await messenger.folders.query(query);
      if (found) return found.id;
    }
  }
  throw new Error(`unknown ${label}`);
}

async function refuseSpecial(folderId) {
  const folder = await messenger.folders.get(folderId);
  if (folder.isRoot || (folder.specialUse ?? []).length) {
    throw new Error("built-in folders can't be renamed, moved or deleted");
  }
}

function vcardValues(vCard, field) {
  const pattern = new RegExp(`^${field}(;[^:]*)?:(.*)$`, "gim");
  return [...(vCard ?? "").matchAll(pattern)].map((m) => m[2].trim());
}

function vcardValue(vCard, field) {
  return vcardValues(vCard, field)[0] ?? "";
}

function vcardEscape(value) {
  return value.replace(/[\\,;]/g, (c) => `\\${c}`).replace(/[\r\n]+/g, " ");
}

function finishSearch(seen, limit, truncated) {
  const messages = [...seen.values()].sort((a, b) => b.date - a.date);
  return {
    messages: messages.slice(0, limit).map(headerSummary),
    matched: messages.length,
    truncated,
  };
}

async function onHostMessage(message) {
  if (message.type === "ping") return;
  const { id, method, params } = message;
  const handler = Object.hasOwn(HANDLERS, method) ? HANDLERS[method] : null;
  try {
    if (!handler) throw new Error(`unknown method: ${method}`);
    port?.postMessage({ id, ok: true, result: await handler(params ?? {}) });
  } catch (error) {
    port?.postMessage({ id, ok: false, error: String(error?.message ?? error) });
  }
}

// Listeners stay at the top level so Thunderbird can wake this page for them.
messenger.messages.onNewMailReceived.addListener((folder, list) => {
  connect();
  if (!folder.specialUse?.includes("inbox")) return;
  // Counts and sender display names only. Subjects, addresses and bodies stay put.
  const messages = list.messages;
  port?.postMessage({
    event: "new_mail",
    account: folder.accountId,
    count: messages.length,
    senders: senderNames(messages),
    career: senderNames(messages.filter(isCareer)),
  });
});
messenger.runtime.onStartup.addListener(connect);
messenger.runtime.onInstalled.addListener(connect);
messenger.alarms.onAlarm.addListener(connect);
messenger.alarms.create("reconnect", { periodInMinutes: 1 });
connect();
