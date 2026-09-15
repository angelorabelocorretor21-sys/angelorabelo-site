// api/_lib/github.js
// Helper compartilhado para ler/gravar o arquivo leads/leads.json no
// repositorio privado configurado em GITHUB_LEADS_REPO.
// (redeploy trigger: forca a Vercel reler as variaveis de ambiente)

const LEADS_PATH = "leads/leads.json";

async function githubRequest(path, options = {}) {
  const token = process.env.GITHUB_TOKEN;
  const repo = process.env.GITHUB_LEADS_REPO;
  if (!token || !repo) {
    throw new Error("GITHUB_TOKEN ou GITHUB_LEADS_REPO nao configurados");
  }
  const url = `https://api.github.com/repos/${repo}/contents/${path}`;
  const resp = await fetch(url, {
    ...options,
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  return resp;
}

async function readLeads() {
  const resp = await githubRequest(LEADS_PATH);
  if (resp.status === 404) {
    return { leads: [], sha: null };
  }
  if (!resp.ok) {
    throw new Error(`Falha ao ler leads.json: ${resp.status}`);
  }
  const data = await resp.json();
  const content = Buffer.from(data.content, "base64").toString("utf-8");
  let leads = [];
  try {
    leads = JSON.parse(content);
  } catch (e) {
    leads = [];
  }
  return { leads, sha: data.sha };
}

async function writeLeads(leads, sha, message) {
  const content = Buffer.from(JSON.stringify(leads, null, 2), "utf-8").toString("base64");
  const body = {
    message,
    content,
    ...(sha ? { sha } : {}),
  };
  const resp = await githubRequest(LEADS_PATH, {
    method: "PUT",
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`Falha ao gravar leads.json: ${resp.status} ${text}`);
  }
}

function checkAdminAuth(req) {
  // Aceita ADMIN_PASSWORD (nome padrao) ou SENHA_DE_ADMINISTRADOR (caso o
  // autocompletar do navegador tenha salvo a variavel com esse nome na Vercel).
  const expected = process.env.ADMIN_PASSWORD || process.env.SENHA_DE_ADMINISTRADOR;
  if (!expected) return false;
  const header = req.headers["x-admin-password"];
  if (header && header === expected) return true;
  const auth = req.headers["authorization"];
  if (auth && auth === `Bearer ${expected}`) return true;
  return false;
}

module.exports = { readLeads, writeLeads, checkAdminAuth, LEADS_PATH };
