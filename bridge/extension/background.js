// Email TUI Bridge. Answers requests from the local native host.
// The manifest grants no send, delete, move or modify permission, so Thunderbird
// rejects those calls even if this file is changed or misused.

const HOST_NAME = "email_tui_bridge";
const MAX_LIMIT = 50;
const SCAN_CAP = 500;
const SCAN_MS = 20000;
const BODY_CHARS = 100000;
const DEFAULT_SINCE_DAYS = 90;

let port = null;

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
    return {
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
};

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
  // Counts only. Subjects and senders never leave without a request.
  port?.postMessage({
    event: "new_mail",
    account: folder.accountId,
    count: list.messages.length,
  });
});
messenger.runtime.onStartup.addListener(connect);
messenger.runtime.onInstalled.addListener(connect);
messenger.alarms.onAlarm.addListener(connect);
messenger.alarms.create("reconnect", { periodInMinutes: 1 });
connect();
