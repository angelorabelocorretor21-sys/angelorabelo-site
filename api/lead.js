// api/lead.js
// Recebe o formulario de contato do site (home e fichas de imovel) e grava
// o lead no arquivo leads/leads.json do repositorio privado de leads.
//
// Variaveis de ambiente necessarias (Vercel > Project > Settings > Environment Variables):
//   GITHUB_TOKEN        - fine-grained PAT com Contents:read/write no repo de leads
//   GITHUB_LEADS_REPO   - "angelorabelocorretor21-sys/rabelo-leads-site"

const { readLeads, writeLeads } = require("./_lib/github");

function jsonResponse(res, status, body) {
  res.status(status).setHeader("Content-Type", "application/json; charset=utf-8");
  res.end(JSON.stringify(body));
}

function isValidPhone(v) {
  const digits = String(v || "").replace(/\D/g, "");
  return digits.length >= 10 && digits.length <= 13;
}

module.exports = async (req, res) => {
  res.setHeader("Access-Control-Allow-Origin", "https://www.angelorabeloimoveis.com.br");
  res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  if (req.method === "OPTIONS") {
    res.status(204).end();
    return;
  }
  if (req.method !== "POST") {
    jsonResponse(res, 405, { ok: false, erro: "Método não permitido" });
    return;
  }

  let body = req.body;
  if (typeof body === "string") {
    try {
      body = JSON.parse(body);
    } catch (e) {
      body = {};
    }
  }
  body = body || {};

  // Honeypot: campo invisível para humanos — se vier preenchido, é bot.
  if (body.website) {
    jsonResponse(res, 200, { ok: true });
    return;
  }

  const nome = String(body.nome || "").trim().slice(0, 200);
  const telefone = String(body.telefone || "").trim().slice(0, 40);
  const email = String(body.email || "").trim().slice(0, 200);
  const mensagem = String(body.mensagem || "").trim().slice(0, 2000);
  const optInMarketing = Boolean(body.optInMarketing);
  const imovelCodigo = String(body.imovelCodigo || "").trim().slice(0, 20) || null;
  const imovelTitulo = String(body.imovelTitulo || "").trim().slice(0, 300) || null;
  const paginaOrigem = String(body.paginaOrigem || "").trim().slice(0, 500) || null;
  const utmSource = String(body.utmSource || "").trim().slice(0, 100) || null;
  const utmCampaign = String(body.utmCampaign || "").trim().slice(0, 100) || null;

  if (!nome || !isValidPhone(telefone)) {
    jsonResponse(res, 400, { ok: false, erro: "Nome e telefone/WhatsApp válidos são obrigatórios." });
    return;
  }

  const lead = {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    nome,
    telefone,
    email: email || null,
    mensagem: mensagem || null,
    opt_in_marketing: optInMarketing,
    imovel_codigo: imovelCodigo,
    imovel_titulo: imovelTitulo,
    pagina_origem: paginaOrigem,
    utm_source: utmSource,
    utm_campaign: utmCampaign,
    criado_em: new Date().toISOString(),
    status: "novo",
  };

  try {
    const { leads, sha } = await readLeads();
    leads.push(lead);
    await writeLeads(leads, sha, `Novo lead: ${nome}${imovelCodigo ? " - " + imovelCodigo : ""}`);
    jsonResponse(res, 200, { ok: true });
  } catch (err) {
    console.error(err);
    jsonResponse(res, 500, {
      ok: false,
      erro: "Não foi possível registrar seu contato agora. Tente novamente ou use o WhatsApp.",
    });
  }
};
