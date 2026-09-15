// api/leads.js
// Lista os leads gravados, para o painel /leads/. Exige a senha do painel
// no header X-Admin-Password (ou Authorization: Bearer <senha>).

const { readLeads, checkAdminAuth } = require("./_lib/github");

module.exports = async (req, res) => {
  if (req.method !== "GET") {
    res.status(405).json({ ok: false, erro: "Método não permitido" });
    return;
  }
  if (!checkAdminAuth(req)) {
    res.status(401).json({ ok: false, erro: "Senha inválida" });
    return;
  }
  try {
    const { leads } = await readLeads();
    leads.sort((a, b) => (a.criado_em < b.criado_em ? 1 : -1));
    res.status(200).json({ ok: true, leads });
  } catch (err) {
    console.error(err);
    res.status(500).json({ ok: false, erro: "Não foi possível carregar os leads." });
  }
};
