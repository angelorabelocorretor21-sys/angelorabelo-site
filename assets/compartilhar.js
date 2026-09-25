/* assets/compartilhar.js — "Enviar imóvel pelo WhatsApp" (home + fichas /imovel/AR-XXXX/)
   - Botão "Enviar" em cada imóvel: abre o WhatsApp para escolher o contato, com a
     mensagem pronta (título, local, preço, código e link da ficha).
   - "Selecionar": junta vários imóveis e envia todos numa única mensagem.
   A seleção fica guardada neste navegador (se o navegador permitir) e vale
   tanto na home quanto nas fichas. Não depende de nenhum outro script. */
(function () {
  if (window.RS) return;
  var SITE = 'https://www.angelorabeloimoveis.com.br';
  var CHAVE = 'rs_selecao_v1';
  var ASSINATURA = '_Angelo Rabêlo Imóveis · CRECI-PE 9560_\n📞 (81) 99383-7490';

  function ev(nome, dados) { try { if (typeof gtag === 'function') gtag('event', nome, dados || {}); } catch (e) {} }
  function urlFicha(cod) { return SITE + '/imovel/' + cod + '/'; }
  function brl(n) { return 'R$ ' + Number(n).toLocaleString('pt-BR', { maximumFractionDigits: 0 }); }

  /* ---------- dados do imóvel ---------- */
  function daLista(cod) {
    try {
      if (typeof IMOVEIS === 'undefined') return null;
      var i = IMOVEIS.find(function (x) { return x.codigoAR === cod || String(x.codigo) === String(cod); });
      if (!i) return null;
      var preco = i.venda ? brl(i.venda) : i.aluguel ? brl(i.aluguel) + '/mês' : i.diaria ? brl(i.diaria) + '/diária' : 'Consulte';
      var f = [];
      if (i.quartos) f.push(i.quartos + (+i.quartos === 1 ? ' quarto' : ' quartos'));
      if (i.suites) f.push(i.suites + (+i.suites === 1 ? ' suíte' : ' suítes'));
      if (i.vagas) f.push(i.vagas + (+i.vagas === 1 ? ' vaga' : ' vagas'));
      var ar = i.areaTotal || i.areaUtil; if (ar) f.push(ar + ' m²');
      return { c: i.codigoAR, t: (i.titulo || '').trim(), l: [i.bairro, i.cidade].filter(Boolean).join(' · '), p: preco, f: f.join(' · ') };
    } catch (e) { return null; }
  }
  function daFicha() {
    var m = location.pathname.match(/\/imovel\/(AR-\d+)\/?/i);
    if (!m) return null;
    function txt(sel) { var el = document.querySelector(sel); return el ? el.textContent.trim() : ''; }
    var f = Array.prototype.map.call(document.querySelectorAll('.feats li'), function (li) { return li.textContent.trim(); })
      .filter(function (s) { return !/banheiro/i.test(s); });
    return { c: m[1].toUpperCase(), t: txt('h1'), l: txt('.loc'), p: txt('.preco') || 'Consulte', f: f.join(' · ') };
  }

  /* ---------- mensagens ---------- */
  function msgUm(d) {
    var s = '🏡 *' + d.t + '*\n';
    if (d.l) s += '📍 ' + d.l + '\n';
    if (d.f) s += '🔑 ' + d.f + '\n';
    s += '💰 *' + d.p + '*\n';
    s += 'Cód. ' + d.c + '\n\n';
    s += '👉 Veja fotos e detalhes:\n' + urlFicha(d.c) + '\n\n' + ASSINATURA;
    return s;
  }
  function msgVarios(lista) {
    if (lista.length === 1) return msgUm(lista[0]);
    var s = 'Olá! Separei ' + lista.length + ' imóveis para você 👇\n';
    lista.forEach(function (d, k) {
      s += '\n*' + (k + 1) + ') ' + d.t + '*\n';
      s += [d.l, d.p].filter(Boolean).join(' · ') + '\n';
      s += urlFicha(d.c) + '\n';
    });
    s += '\nToque em cada link para ver as fotos e os detalhes.\n\n' + ASSINATURA;
    return s;
  }
  function abrirWhats(texto) {
    var url = 'https://wa.me/?text=' + encodeURIComponent(texto);
    var w = window.open(url, '_blank');
    if (!w) location.href = url;
  }
  function copiar(texto, okMsg) {
    function fb() {
      var ta = document.createElement('textarea'); ta.value = texto; ta.setAttribute('readonly', '');
      ta.style.position = 'fixed'; ta.style.opacity = '0'; document.body.appendChild(ta); ta.select();
      try { document.execCommand('copy'); aviso(okMsg); } catch (e) { aviso('Não foi possível copiar'); }
      document.body.removeChild(ta);
    }
    if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(texto).then(function () { aviso(okMsg); }, fb);
    else fb();
  }

  /* ---------- seleção ---------- */
  var sel = [];
  try { sel = JSON.parse(localStorage.getItem(CHAVE) || '[]') || []; } catch (e) { sel = []; }
  function salvar() { try { localStorage.setItem(CHAVE, JSON.stringify(sel)); } catch (e) {} }
  function idx(cod) { for (var k = 0; k < sel.length; k++) if (sel[k].c === cod) return k; return -1; }
  function dados(cod) { return daLista(cod) || ((daFicha() || {}).c === cod ? daFicha() : null); }

  function toggle(cod, origem) {
    var k = idx(cod);
    if (k > -1) { sel.splice(k, 1); }
    else { var d = dados(cod); if (!d) return; sel.push(d); ev('selecionar_imovel', { codigo: cod, origem: origem || 'card' }); }
    salvar(); pintar();
  }
  function limpar() { sel = []; salvar(); pintar(); }

  function enviar(cod, origem) {
    var d = dados(cod); if (!d) return;
    ev('enviar_imovel', { codigo: cod, origem: origem || 'card' });
    abrirWhats(msgUm(d));
  }
  function enviarSelecao() {
    if (!sel.length) return;
    ev('enviar_selecao', { quantidade: sel.length, codigos: sel.map(function (d) { return d.c; }).join(',') });
    abrirWhats(msgVarios(sel));
  }

  /* ---------- interface ---------- */
  var CSS =
    '.rs-acoes{display:flex;gap:8px;margin-top:14px;flex-wrap:wrap}' +
    '.rs-b{font:500 13px/1 Jost,-apple-system,sans-serif;letter-spacing:.02em;border-radius:4px;padding:10px 14px;cursor:pointer;border:1px solid #9c7622;background:transparent;color:#7a5c19;display:inline-flex;align-items:center;gap:6px;text-decoration:none;min-height:40px;transition:.2s}' +
    '.rs-b:hover{background:#9c7622;color:#fff}' +
    '.rs-b.rs-env{background:#117a4a;border-color:#117a4a;color:#fff}' +
    '.rs-b.rs-env:hover{background:#0d6139;border-color:#0d6139}' +
    '.rs-b.rs-on{background:#9c7622;color:#fff}' +
    '.rs-bar{position:fixed;left:50%;bottom:18px;transform:translate(-50%,160%);z-index:310;background:#2c2620;color:#fff;border-radius:10px;box-shadow:0 14px 40px rgba(0,0,0,.35);display:flex;align-items:center;gap:10px;padding:10px 12px 10px 18px;font:400 14px/1.2 Jost,-apple-system,sans-serif;transition:transform .3s;max-width:calc(100vw - 24px)}' +
    '.rs-bar.show{transform:translate(-50%,0)}' +
    '.rs-bar b{color:#e0bf72;font-weight:600}' +
    '.rs-bar .rs-b{border-color:rgba(255,255,255,.35);color:#fff}' +
    '.rs-bar .rs-b.rs-env{border-color:#117a4a}' +
    '.rs-bar .rs-x{background:none;border:0;color:#bfb3a0;font-size:22px;cursor:pointer;padding:0 4px;line-height:1}' +
    '.rs-lista{position:fixed;left:50%;bottom:84px;transform:translateX(-50%);z-index:309;background:#fff;color:#2c2620;border-radius:10px;box-shadow:0 14px 40px rgba(0,0,0,.3);width:min(420px,calc(100vw - 24px));max-height:50vh;overflow:auto;padding:8px 0;display:none;font:400 14px/1.35 Jost,-apple-system,sans-serif}' +
    '.rs-lista.show{display:block}' +
    '.rs-lista div{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:8px 16px;border-bottom:1px solid #f0e8d8}' +
    '.rs-lista div:last-child{border-bottom:0}' +
    '.rs-lista small{display:block;color:#867c69;font-size:12px}' +
    '.rs-lista button{background:none;border:0;color:#a33;font-size:20px;cursor:pointer;line-height:1}' +
    '.rs-toast{position:fixed;left:50%;top:22px;transform:translateX(-50%);z-index:320;background:#2c2620;color:#fff;padding:10px 18px;border-radius:6px;font:400 14px Jost,-apple-system,sans-serif;box-shadow:0 8px 24px rgba(0,0,0,.3);opacity:0;transition:opacity .25s;pointer-events:none;max-width:calc(100vw - 32px);text-align:center}' +
    '.rs-toast.show{opacity:1}' +
    'body.rs-com-barra .wa{bottom:92px}' +
    '.lb .rs-acoes{justify-content:flex-end}.lb .rs-b{color:#fff;border-color:rgba(255,255,255,.45)}.lb .rs-b.rs-env{border-color:#117a4a}.lb .rs-b.rs-on{background:#9c7622;border-color:#9c7622}' +
    '@media(max-width:600px){.rs-bar{left:12px;right:12px;transform:translateY(160%);bottom:12px;padding:10px;gap:6px}.rs-bar.show{transform:none}' +
    '.rs-bar .rs-txt{flex:1;font-size:13px}.rs-bar .rs-b{padding:10px 10px;font-size:12px}.rs-bar .rs-copiar{display:none}.rs-lista{bottom:78px}}';

  var barra, lista, toastEl, toastT;
  function aviso(t) {
    if (!toastEl) { toastEl = document.createElement('div'); toastEl.className = 'rs-toast'; document.body.appendChild(toastEl); }
    toastEl.textContent = t; toastEl.classList.add('show');
    clearTimeout(toastT); toastT = setTimeout(function () { toastEl.classList.remove('show'); }, 2600);
  }
  function montarUI() {
    var st = document.createElement('style'); st.textContent = CSS; document.head.appendChild(st);
    barra = document.createElement('div'); barra.className = 'rs-bar'; barra.setAttribute('role', 'region'); barra.setAttribute('aria-label', 'Imóveis selecionados');
    barra.innerHTML =
      '<span class="rs-txt"><b class="rs-n">0</b> <a href="#" class="rs-ver" style="color:inherit;text-decoration:underline">selecionado(s)</a></span>' +
      '<button type="button" class="rs-b rs-env rs-go">📲 Enviar no WhatsApp</button>' +
      '<button type="button" class="rs-b rs-copiar">Copiar</button>' +
      '<button type="button" class="rs-x" title="Limpar seleção" aria-label="Limpar seleção">×</button>';
    document.body.appendChild(barra);
    lista = document.createElement('div'); lista.className = 'rs-lista'; document.body.appendChild(lista);
    barra.querySelector('.rs-go').onclick = enviarSelecao;
    barra.querySelector('.rs-copiar').onclick = function () { copiar(msgVarios(sel), 'Mensagem copiada — cole no WhatsApp'); };
    barra.querySelector('.rs-x').onclick = function () { lista.classList.remove('show'); limpar(); };
    barra.querySelector('.rs-ver').onclick = function (e) { e.preventDefault(); lista.classList.toggle('show'); };
    lista.addEventListener('click', function (e) {
      var b = e.target.closest('button[data-c]'); if (b) toggle(b.getAttribute('data-c'));
    });
  }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function pintar() {
    if (!barra) return;
    var n = sel.length;
    barra.querySelector('.rs-n').textContent = n;
    barra.querySelector('.rs-ver').textContent = n === 1 ? 'selecionado' : 'selecionados';
    barra.querySelector('.rs-go').textContent = n > 1 ? '📲 Enviar os ' + n : '📲 Enviar no WhatsApp';
    barra.classList.toggle('show', n > 0);
    document.body.classList.toggle('rs-com-barra', n > 0);
    if (!n) lista.classList.remove('show');
    lista.innerHTML = sel.map(function (d) {
      return '<div><span>' + esc(d.t) + '<small>' + esc(d.c) + ' · ' + esc(d.p) + '</small></span>' +
        '<button type="button" data-c="' + esc(d.c) + '" title="Tirar da seleção" aria-label="Tirar da seleção">×</button></div>';
    }).join('');
    Array.prototype.forEach.call(document.querySelectorAll('[data-rs-sel]'), function (b) {
      var on = idx(b.getAttribute('data-rs-sel')) > -1;
      b.classList.toggle('rs-on', on);
      b.textContent = on ? '✓ Selecionado' : '＋ Selecionar';
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
  }

  /* HTML dos botões para os cards/lightbox da home */
  function botoes(cod, origem) {
    cod = esc(cod); origem = origem || 'card';
    return '<div class="rs-acoes">' +
      '<button type="button" class="rs-b rs-env" title="Enviar este imóvel pelo WhatsApp" onclick="event.stopPropagation();RS.enviar(\'' + cod + '\',\'' + origem + '\')">📲 Enviar</button>' +
      '<button type="button" class="rs-b" data-rs-sel="' + cod + '" aria-pressed="false" title="Juntar com outros imóveis para enviar numa só mensagem" onclick="event.stopPropagation();RS.toggle(\'' + cod + '\',\'' + origem + '\')">＋ Selecionar</button>' +
      '</div>';
  }

  /* Ficha individual: injeta os botões abaixo do preço */
  function montarFicha() {
    var d = daFicha(); if (!d) return;
    var alvo = document.querySelector('.loc') || document.querySelector('h1');
    if (!alvo || document.querySelector('.rs-ficha')) return;
    var box = document.createElement('div'); box.className = 'rs-acoes rs-ficha'; box.style.margin = '0 0 20px';
    box.innerHTML =
      '<button type="button" class="rs-b rs-env">📲 Enviar este imóvel</button>' +
      '<button type="button" class="rs-b" data-rs-sel="' + esc(d.c) + '" aria-pressed="false">＋ Selecionar</button>' +
      '<button type="button" class="rs-b rs-link">🔗 Copiar link</button>';
    alvo.parentNode.insertBefore(box, alvo.nextSibling);
    box.querySelector('.rs-env').onclick = function () { enviar(d.c, 'ficha'); };
    box.querySelector('[data-rs-sel]').onclick = function () { toggle(d.c, 'ficha'); };
    box.querySelector('.rs-link').onclick = function () { copiar(urlFicha(d.c), 'Link copiado'); ev('copiar_link_imovel', { codigo: d.c }); };
  }

  window.RS = { enviar: enviar, toggle: toggle, limpar: limpar, botoes: botoes, pintar: pintar, aviso: aviso, enviarSelecao: enviarSelecao };

  function iniciar() {
    montarUI();
    montarFicha();
    pintar();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', iniciar);
  else iniciar();
})();
