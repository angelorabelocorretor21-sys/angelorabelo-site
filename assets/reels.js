/* assets/reels.js — vídeos dos Reels no site.
   Lê /assets/reels/reels.json (gerado pelo workflow reels-site) e mostra:
   - página inicial: seção "Vídeos dos imóveis" logo depois de "Imóveis selecionados",
     selo "▶ Vídeo" nos cards e botão "Assistir ao vídeo" no visualizador de fotos;
   - ficha /imovel/AR-XXXX/: o vídeo antes das fotos.
   Carregado pelo lead.js (home e fichas). Não depende de nenhum outro script. */
(function () {
  if (window.__reelsSite) return;
  window.__reelsSite = true;

  var CSS =
    ".rv-sec{padding:72px 0;background:#12100d;color:#f2ece0}" +
    ".rv-sec .rv-head{text-align:center;max-width:640px;margin:0 auto 34px;padding:0 24px}" +
    ".rv-sec .rv-eb{font-size:12px;letter-spacing:.32em;text-transform:uppercase;color:#c9a24b;font-weight:500}" +
    ".rv-sec h2{font-family:'Cormorant Garamond',serif;font-size:clamp(30px,5vw,48px);font-weight:600;color:#fff;margin:12px 0 8px;line-height:1.1}" +
    ".rv-sec .rv-head p{color:#cfc4ae;font-size:16px;margin:0}" +
    ".rv-row{display:flex;gap:16px;overflow-x:auto;scroll-snap-type:x mandatory;padding:4px 24px 18px;max-width:1248px;margin:0 auto;-webkit-overflow-scrolling:touch;scrollbar-width:thin}" +
    ".rv-card{flex:0 0 200px;scroll-snap-align:start;cursor:pointer;background:none;border:0;padding:0;text-align:left;color:inherit;font:inherit}" +
    ".rv-thumb{position:relative;aspect-ratio:9/16;border-radius:10px;overflow:hidden;background:#2a241b center/cover no-repeat;box-shadow:0 10px 26px rgba(0,0,0,.35);transition:transform .25s}" +
    ".rv-card:hover .rv-thumb,.rv-card:focus-visible .rv-thumb{transform:translateY(-4px)}" +
    ".rv-play{position:absolute;left:50%;top:50%;width:58px;height:58px;margin:-29px 0 0 -29px;border-radius:50%;background:rgba(18,16,13,.55);border:2px solid rgba(255,255,255,.85);display:flex;align-items:center;justify-content:center}" +
    ".rv-play:after{content:'';margin-left:5px;border-style:solid;border-width:11px 0 11px 18px;border-color:transparent transparent transparent #fff}" +
    ".rv-dur{position:absolute;right:8px;bottom:8px;background:rgba(0,0,0,.6);color:#fff;font-size:12px;padding:2px 8px;border-radius:12px}" +
    ".rv-t{font-size:14px;line-height:1.35;margin-top:10px;color:#f2ece0;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}" +
    ".rv-s{font-size:12px;color:#c9a24b;letter-spacing:.06em;margin-top:2px}" +
    ".rv-ov{position:fixed;inset:0;z-index:400;background:rgba(10,8,6,.94);display:none;align-items:center;justify-content:center;flex-direction:column;padding:16px}" +
    ".rv-ov.open{display:flex}" +
    ".rv-ov video{max-height:78vh;max-width:min(92vw,440px);aspect-ratio:9/16;border-radius:10px;background:#000;display:block}" +
    ".rv-x{position:absolute;top:8px;right:12px;z-index:2;width:48px;height:48px;background:rgba(0,0,0,.55);border:0;border-radius:50%;color:#fff;font-size:34px;line-height:1;cursor:pointer}" +
    ".rv-info{margin-top:14px;text-align:center;color:#f2ece0;max-width:440px}" +
    ".rv-info b{display:block;font-family:'Cormorant Garamond',serif;font-size:21px;font-weight:600;line-height:1.2}" +
    ".rv-acts{display:flex;gap:10px;justify-content:center;flex-wrap:wrap;margin-top:12px}" +
    ".rv-btn{display:inline-block;padding:11px 20px;border-radius:4px;font-size:14px;font-weight:500;text-decoration:none;cursor:pointer;border:1px solid #c9a24b}" +
    ".rv-btn.g{background:#c9a24b;color:#1a150c}.rv-btn.o{background:transparent;color:#e7cf8f}" +
    ".rv-badge{position:absolute;top:14px;right:14px;z-index:3;background:rgba(18,16,13,.72);color:#fff;font-size:11px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;padding:5px 10px;border-radius:2px}" +
    ".rv-lbbtn{margin:10px 0 0;background:transparent;border:1px solid #c9a24b;color:#e7cf8f;padding:9px 16px;border-radius:4px;font-family:inherit;font-size:14px;cursor:pointer}" +
    ".rv-lbbtn:hover{background:#c9a24b;color:#1a150c}" +
    ".rv-ficha{margin:0 0 18px;display:flex;gap:18px;align-items:center;flex-wrap:wrap;background:#12100d;border-radius:12px;padding:16px}" +
    ".rv-ficha video{width:100%;max-width:300px;aspect-ratio:9/16;border-radius:10px;background:#000;display:block;margin:0 auto}" +
    ".rv-ficha .rv-ftxt{flex:1;min-width:200px;color:#f2ece0;font-size:15px}" +
    ".rv-ficha .rv-ftxt b{display:block;font-family:'Cormorant Garamond',serif;font-size:24px;color:#e7cf8f;font-weight:600;margin-bottom:4px}" +
    "@media(max-width:600px){.rv-sec{padding:52px 0}.rv-card{flex-basis:46vw}.rv-ficha{padding:10px}.rv-ficha .rv-ftxt{display:none}}";

  function ev(nome, codigo, origem) {
    try { if (window.gtag) gtag("event", nome, { codigo: codigo, origem: origem }); } catch (e) {}
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function dur(s) {
    s = Math.round(s || 0);
    return s ? Math.floor(s / 60) + ":" + ("0" + (s % 60)).slice(-2) : "";
  }
  function estilo() {
    var st = document.createElement("style");
    st.textContent = CSS;
    document.head.appendChild(st);
  }
  function imoveisDaPagina() {
    try { return typeof IMOVEIS !== "undefined" && Array.isArray(IMOVEIS) ? IMOVEIS : null; } catch (e) { return null; }
  }
  function local(i) {
    return [i.bairro, i.cidade].filter(Boolean).join(" · ");
  }

  /* ---------- player em tela cheia (home) ---------- */
  var ov, ovVideo, ovInfo;
  function player() {
    if (ov) return;
    ov = document.createElement("div");
    ov.className = "rv-ov";
    ov.setAttribute("role", "dialog");
    ov.setAttribute("aria-label", "Vídeo do imóvel");
    ov.innerHTML = '<button class="rv-x" aria-label="Fechar">×</button><video controls playsinline preload="none"></video><div class="rv-info"></div>';
    document.body.appendChild(ov);
    ovVideo = ov.querySelector("video");
    ovInfo = ov.querySelector(".rv-info");
    ov.querySelector(".rv-x").onclick = fechar;
    ov.addEventListener("click", function (e) { if (e.target === ov) fechar(); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && ov.classList.contains("open")) fechar(); });
  }
  function fechar() {
    ovVideo.pause();
    ovVideo.removeAttribute("src");
    ovVideo.load();
    ov.classList.remove("open");
    if (!document.getElementById("lb") || !document.getElementById("lb").classList.contains("open")) document.body.style.overflow = "";
  }
  function abrir(r, i, origem) {
    player();
    ovVideo.poster = r.capa;
    ovVideo.src = r.video;
    var wa = "https://wa.me/5581993837490?text=" + encodeURIComponent("Olá Angelo, vi o vídeo do imóvel " + r.codigo + (i ? " (" + i.titulo + ")" : "") + " no site e quero mais informações.\n\nhttps://www.angelorabeloimoveis.com.br/imovel/" + r.codigo + "/");
    ovInfo.innerHTML = (i ? "<b>" + esc(i.titulo) + "</b><span>" + esc(local(i)) + " · Cód. " + r.codigo + "</span>" : "<b>Cód. " + r.codigo + "</b>") +
      '<div class="rv-acts"><a class="rv-btn g" target="_blank" rel="noopener" href="' + wa + '">Falar no WhatsApp</a>' +
      '<a class="rv-btn o" href="/imovel/' + r.codigo + '/">Ver fotos e detalhes</a></div>';
    ovInfo.querySelector(".rv-btn.g").addEventListener("click", function () { ev("clique_whatsapp", r.codigo, "video"); });
    ov.classList.add("open");
    document.body.style.overflow = "hidden";
    var p = ovVideo.play();
    if (p && p.catch) p.catch(function () {});
    ev("ver_video", r.codigo, origem);
  }

  /* ---------- página inicial ---------- */
  function home(lista, imoveis) {
    var porCod = {};
    imoveis.forEach(function (i) { if (i.codigoAR) porCod[i.codigoAR] = i; });
    var itens = lista.filter(function (r) { return porCod[r.codigo]; });
    if (!itens.length) return;
    var mapa = {};
    itens.forEach(function (r) { mapa[r.codigo] = r; });

    // seção "Vídeos dos imóveis"
    var alvo = document.getElementById("imoveis");
    if (alvo && !document.getElementById("videos")) {
      var sec = document.createElement("section");
      sec.id = "videos";
      sec.className = "rv-sec";
      sec.innerHTML = '<div class="rv-head"><div class="rv-eb">Assista</div><h2>Vídeos dos imóveis</h2>' +
        "<p>Conheça cada imóvel em menos de um minuto — os mesmos vídeos do nosso Instagram.</p></div>" +
        '<div class="rv-row">' + itens.map(function (r) {
          var i = porCod[r.codigo];
          return '<button type="button" class="rv-card" data-cod="' + r.codigo + '" aria-label="Assistir ao vídeo: ' + esc(i.titulo) + '">' +
            '<div class="rv-thumb" style="background-image:url(\'' + r.capa + '\')"><span class="rv-play"></span>' +
            (r.duracao ? '<span class="rv-dur">' + dur(r.duracao) + "</span>" : "") + "</div>" +
            '<div class="rv-t">' + esc(i.titulo) + '</div><div class="rv-s">' + esc(i.cidade || "") + " · " + r.codigo + "</div></button>";
        }).join("") + "</div>";
      alvo.parentNode.insertBefore(sec, alvo.nextSibling);
      sec.addEventListener("click", function (e) {
        var b = e.target.closest(".rv-card");
        if (b) abrir(mapa[b.dataset.cod], porCod[b.dataset.cod], "secao_videos");
      });
    }

    // selo "▶ Vídeo" nos cards
    var rjweb = {};
    imoveis.forEach(function (i) { rjweb[String(i.codigo)] = i.codigoAR; });
    function selos() {
      var cards = document.querySelectorAll("#grid-imoveis .card");
      for (var k = 0; k < cards.length; k++) {
        var c = cards[k];
        if (c.__rv) continue;
        c.__rv = 1;
        var m = (c.getAttribute("onclick") || "").match(/openLB\('([^']+)'\)/);
        var ar = m && rjweb[m[1]];
        var img = c.querySelector(".img");
        if (ar && mapa[ar] && img) {
          var s = document.createElement("span");
          s.className = "rv-badge";
          s.textContent = "▶ Vídeo";
          img.appendChild(s);
        }
      }
    }
    var grid = document.getElementById("grid-imoveis");
    if (grid && window.MutationObserver) new MutationObserver(selos).observe(grid, { childList: true });
    selos();

    // botão no visualizador de fotos
    var original = window.openLB;
    if (typeof original === "function") {
      window.openLB = function (codigo) {
        var r = original.apply(this, arguments);
        try {
          var lb = document.getElementById("lb");
          var velho = lb && lb.querySelector(".rv-lbbtn");
          if (velho) velho.remove();
          var i = imoveis.find(function (x) { return String(x.codigo) === String(codigo); });
          var v = i && mapa[i.codigoAR];
          var lugar = document.getElementById("lb-wa");
          if (v && lugar) {
            var b = document.createElement("button");
            b.type = "button";
            b.className = "rv-lbbtn";
            b.textContent = "▶ Assistir ao vídeo";
            b.onclick = function () { abrir(v, i, "visualizador"); };
            lugar.insertAdjacentElement("afterend", b);
            lugar.parentNode.insertBefore(document.createElement("br"), b);
          }
        } catch (e) {}
        return r;
      };
    }
  }

  /* ---------- ficha /imovel/AR-XXXX/ ---------- */
  function ficha(lista, codigo) {
    var r = lista.filter(function (x) { return x.codigo === codigo; })[0];
    var capa = document.querySelector("img.capa");
    if (!r || !capa || document.querySelector(".rv-ficha")) return;
    var box = document.createElement("div");
    box.className = "rv-ficha";
    box.innerHTML = '<video controls playsinline preload="metadata" poster="' + r.capa + '" src="' + r.video + '"></video>' +
      '<div class="rv-ftxt"><b>Assista ao vídeo</b>Um tour rápido pelo imóvel — o mesmo vídeo publicado no nosso Instagram. Gostou? Fale comigo pelo WhatsApp e agende sua visita.</div>';
    capa.parentNode.insertBefore(box, capa);
    var vid = box.querySelector("video");
    vid.addEventListener("play", function once() { vid.removeEventListener("play", once); ev("ver_video", codigo, "ficha"); });
  }

  function iniciar() {
    var m = location.pathname.match(/\/imovel\/(AR-\d{4})\/?/i);
    var imoveis = imoveisDaPagina();
    if (!m && !imoveis) return;
    fetch("/assets/reels/reels.json", { cache: "no-cache" })
      .then(function (r) { return r.ok ? r.json() : []; })
      .then(function (lista) {
        if (!Array.isArray(lista) || !lista.length) return;
        estilo();
        if (m) ficha(lista, m[1].toUpperCase());
        else home(lista, imoveis);
      })
      .catch(function () {});
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", iniciar);
  else iniciar();
})();
