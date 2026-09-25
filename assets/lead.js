/* assets/lead.js — formulário de contato compartilhado (home + fichas de imóvel)
   Detecta sozinho o código do imóvel pela URL (/imovel/AR-XXXX/) quando existe.
   Envia para /api/lead. Não depende de nenhum outro script da página. */
(function () {
  function detectImovel() {
    var m = location.pathname.match(/\/imovel\/([A-Za-z0-9-]+)\/?/);
    if (!m) return { codigo: null, titulo: null };
    var codigo = m[1];
    var h1 = document.querySelector("h1");
    var titulo = h1 ? h1.textContent.trim() : document.title;
    return { codigo: codigo, titulo: titulo };
  }

  function getParam(name) {
    try {
      return new URLSearchParams(location.search).get(name) || "";
    } catch (e) {
      return "";
    }
  }

  function formHTML(imovel) {
    var introTitulo = imovel.codigo
      ? "Quero saber mais sobre este imóvel"
      : "Fale com Angelo Rabêlo";
    var introSub = imovel.codigo
      ? "Cód. " + imovel.codigo + " — responda os campos abaixo e te chamo em instantes."
      : "Deixe seus dados que te retorno o quanto antes — ou fale direto pelo WhatsApp.";
    return (
      '<h2 class="lead-h">' + introTitulo + "</h2>" +
      '<p class="lead-sub">' + introSub + "</p>" +
      '<form class="lead-grid" novalidate>' +
      '<div class="lead-field full"><label for="lead-nome">Nome</label>' +
      '<input id="lead-nome" name="nome" type="text" autocomplete="name" required maxlength="200"></div>' +
      '<div class="lead-field"><label for="lead-telefone">WhatsApp / telefone</label>' +
      '<input id="lead-telefone" name="telefone" type="tel" autocomplete="tel" required placeholder="(81) 90000-0000" maxlength="40"></div>' +
      '<div class="lead-field"><label for="lead-email">E-mail (opcional)</label>' +
      '<input id="lead-email" name="email" type="email" autocomplete="email" maxlength="200"></div>' +
      '<div class="lead-field full"><label for="lead-mensagem">Mensagem</label>' +
      '<textarea id="lead-mensagem" name="mensagem" maxlength="2000" placeholder="' +
      (imovel.codigo ? "Quero agendar uma visita, saber mais sobre condições de pagamento..." : "Como posso te ajudar?") +
      '"></textarea></div>' +
      '<label class="lead-opt"><input type="checkbox" name="optInMarketing"> Quero receber novas oportunidades de imóveis pelo WhatsApp ou e-mail.</label>' +
      '<input class="lead-hp" type="text" name="website" tabindex="-1" autocomplete="off" aria-hidden="true">' +
      '<button class="lead-submit" type="submit">Enviar</button>' +
      '<p class="lead-msg" role="status"></p>' +
      "</form>"
    );
  }

  function mount() {
    var host = document.getElementById("lead-form-mount");
    if (!host) {
      var cta = document.querySelector(".cta");
      if (!cta) return;
      host = document.createElement("div");
      host.id = "lead-form-mount";
      cta.parentNode.insertBefore(host, cta.nextSibling);
    }
    host.className = (host.className ? host.className + " " : "") + "lead-box";

    var imovel = detectImovel();
    host.innerHTML = formHTML(imovel);

    var form = host.querySelector("form");
    var msg = host.querySelector(".lead-msg");
    var btn = host.querySelector(".lead-submit");

    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      msg.className = "lead-msg";
      var fd = new FormData(form);
      var payload = {
        nome: fd.get("nome"),
        telefone: fd.get("telefone"),
        email: fd.get("email"),
        mensagem: fd.get("mensagem"),
        optInMarketing: fd.get("optInMarketing") === "on",
        website: fd.get("website"),
        imovelCodigo: imovel.codigo,
        imovelTitulo: imovel.titulo,
        paginaOrigem: location.href,
        utmSource: getParam("utm_source"),
        utmCampaign: getParam("utm_campaign"),
      };
      btn.disabled = true;
      btn.textContent = "Enviando…";
      fetch("/api/lead", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      })
        .then(function (r) {
          return r.json().then(function (data) {
            return { ok: r.ok, data: data };
          });
        })
        .then(function (res) {
          if (res.ok && res.data.ok) {
            form.reset();
            msg.textContent = "Recebido! Vou te responder em breve — se preferir, fale agora mesmo pelo WhatsApp acima.";
            msg.className = "lead-msg show ok";
            if (typeof gtag === "function") {
              gtag("event", "lead_formulario", { codigo: imovel.codigo || "(geral)" });
            }
          } else {
            msg.textContent = (res.data && res.data.erro) || "Não foi possível enviar agora. Tente pelo WhatsApp.";
            msg.className = "lead-msg show err";
          }
        })
        .catch(function () {
          msg.textContent = "Sem conexão no momento. Tente novamente ou use o WhatsApp.";
          msg.className = "lead-msg show err";
        })
        .finally(function () {
          btn.disabled = false;
          btn.textContent = "Enviar";
        });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }
})();

/* Botões "Enviar imóvel pelo WhatsApp" — nas fichas carrega assets/compartilhar.js
   (a home já inclui o script diretamente). */
(function () {
  if (window.RS || document.querySelector('script[src*="compartilhar.js"]')) return;
  var s = document.createElement("script");
  s.src = "/assets/compartilhar.js";
  s.defer = true;
  document.head.appendChild(s);
})();
