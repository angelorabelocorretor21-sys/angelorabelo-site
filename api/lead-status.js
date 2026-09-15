// api/lead-status.js
// Atualiza o status de um lead (novo / contatado / qualificado / descartado).
// Exige a senha do painel no header X-Admin-Password.

const { readLeads, writeLeads, checkAdminAuth } = require("./_lib/github");

const STATUS_VALIDOS = ["novo", "contatado", "qualificado", "descartado"];

module.exports = async (req, res) => {
  if (req.method !== "POST") {
    res.status(405).json({ ok: false, erro: "Método não permitido" });
    return;
  }
  if (!checkAdminAuth(req)) {
    res.status(401).json({ ok: false, erro: "Senha inválida" });
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

  const { id, status } = body;
  if (!id || !STATUS_VALIDOS.includes(status)) {
    res.status(400).json({ ok: false, erro: "id e status válidos são obrigatórios." });
    return;
  }

  try {
    const { leads, sha } = await readLeads();
    const lead = leads.find((l) => l.id === id);
    if (!lead) {
      res.status(404).json({ ok: false, erro: "Lead não encontrado." });
      return;
    }
    lead.status = status;
    lead.atualizado_em = new Date().toISOString();
    await writeLeads(leads, sha, `Status atualizado: ${lead.nome} -> ${status}`);
    res.status(200).json({ ok: true });
  } catch (err) {
    console.error(err);
    res.status(500).json({ ok: false, erro: "Não foi possível atualizar o status." });
  }
};
