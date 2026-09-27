#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
catalogo.py — mantém o catálogo Meta / WhatsApp Business sempre igual ao site, sem Mac e sem Claude.

Roda no GitHub Actions (workflow catalogo-meta: todo dia às 06:52 e a cada atualização do index.html).
1. Miniatura 1080x1080 (catalogo/img/AR-XXXX.jpg) de cada imóvel: gera as que faltam e REFAZ as de imóveis
   cujo preço/título/tipo/local/fichas mudaram (controle em catalogo/img/hashes.json).
2. Feed da Meta (catalogo/meta-feed.csv), que a Meta busca sozinha todo dia às 18:10.

Fora do catálogo: imóveis sem preço ("sob consulta"), AR-0034 e AR-0108 (nunca divulgar) e AR-0096 (preço suspeito).
Uso: python3 ferramentas/catalogo/catalogo.py   (variável CHROME = caminho do Chrome/Chromium)
"""
import csv, hashlib, html, io, json, os, re, subprocess, sys, tempfile, urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(os.path.dirname(AQUI))
IMG = os.path.join(SITE, "catalogo", "img")
BASE = "https://www.angelorabeloimoveis.com.br"
FORA = {"AR-0034", "AR-0108", "AR-0096"}
CHROME = os.environ.get("CHROME") or "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def imoveis():
    s = open(os.path.join(SITE, "index.html"), encoding="utf-8").read()
    i = s.index("[", s.index("const IMOVEIS"))
    return json.JSONDecoder().raw_decode(s[i:])[0]


def brl(v):
    return "R$ " + f"{v:,.0f}".replace(",", ".")


def preco_label(x):
    if x.get("venda"):
        return brl(x["venda"]), "À VENDA"
    if x.get("aluguel"):
        return brl(x["aluguel"]) + "<small>/mês</small>", "PARA ALUGAR"
    if x.get("diaria"):
        return brl(x["diaria"]) + "<small>/diária</small>", "TEMPORADA"
    return "Sob consulta", "À VENDA"


def specs(x):
    out = []
    def n(k, s, p):
        v = x.get(k)
        if v: out.append(f"{int(float(v))} {s if int(float(v)) == 1 else p}")
    n("quartos", "quarto", "quartos"); n("suites", "suíte", "suítes"); n("vagas", "vaga", "vagas")
    area = x.get("areaUtil") or x.get("areaTotal")
    if area:
        a = float(area)
        out.append(f"{a/10000:,.1f} ha".replace(".", ",") if a >= 10000 else f"{a:,.0f} m²".replace(",", "."))
    return " · ".join(out[:3])


def assinatura(x):
    campos = [x.get(k) for k in ("titulo", "tipo", "cidade", "bairro", "venda", "aluguel", "diaria",
                                 "quartos", "suites", "vagas", "areaUtil", "areaTotal", "foto")]
    return hashlib.md5(json.dumps(campos, ensure_ascii=False, default=str).encode()).hexdigest()[:12]


def capa(x, tmp):
    """Foto de capa sem as faixas pretas: capa local do site → capa extra → 1ª foto do cadastro."""
    from PIL import Image
    ar = x["codigoAR"]
    src = None
    for p in (os.path.join(SITE, "assets", "imoveis", ar + ".jpg"), os.path.join(SITE, "catalogo", "fontes", ar + ".jpg")):
        if os.path.exists(p):
            src = Image.open(p); break
    if src is None:
        for u in ([x["foto"]] if x.get("foto") else []) + list(x.get("fotos") or [])[:3]:
            try:
                req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0 RabeloCatalogo/1.0"})
                src = Image.open(io.BytesIO(urllib.request.urlopen(req, timeout=30).read())); break
            except Exception:
                continue
    if src is None:
        return None
    im = src.convert("RGB")
    g = im.convert("L")
    w, h = g.size
    px = g.load()
    def escura(y):
        vals = [px[xx, y] for xx in range(0, w, max(1, w // 60))]
        m = sum(vals) / len(vals)
        return m < 18 and max(vals) - min(vals) < 30
    t = 0
    while t < h - 1 and escura(t): t += 1
    b = 0
    while b < h - t - 1 and escura(h - 1 - b): b += 1
    dst = os.path.join(tmp, ar + "_capa.jpg")
    im.crop((0, t, w, h - b)).save(dst, "JPEG", quality=95)
    return dst


def render(x, foto, tmp):
    from PIL import Image
    ar = x["codigoAR"]
    preco, fin = preco_label(x)
    local = x.get("cidade") or ""
    if x.get("bairro"): local = f"{x['bairro']} · {local}"
    rep = {"{{LOGO}}": "file://" + os.path.join(AQUI, "logo.png"), "{{FOTO}}": "file://" + foto, "{{AR}}": ar,
           "{{TIPO}}": html.escape((x.get("tipo") or "").upper()), "{{LOCAL}}": html.escape(local.upper()),
           "{{TITULO}}": html.escape(x.get("titulo") or ""), "{{PRECO}}": preco, "{{FINALIDADE}}": fin,
           "{{SPECS}}": html.escape(specs(x))}
    h = open(os.path.join(AQUI, "template.html"), encoding="utf-8").read()
    for k, v in rep.items():
        h = h.replace(k, v)
    hp = os.path.join(tmp, ar + ".html"); open(hp, "w", encoding="utf-8").write(h)
    png = os.path.join(tmp, ar + ".png")
    subprocess.run([CHROME, "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
                    "--force-device-scale-factor=1", "--window-size=1080,1240", "--virtual-time-budget=5000",
                    "--allow-file-access-from-files", "--screenshot=" + png, "file://" + hp],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90)
    Image.open(png).convert("RGB").crop((0, 0, 1080, 1080)).save(os.path.join(IMG, ar + ".jpg"), "JPEG", quality=86)


def descricao(x):
    d = (x.get("descricao") or "").split("\n— ")[0].split("\n—")[0]
    linhas = [l.strip() for l in d.split("\n") if l.strip()]
    if linhas and linhas[0].upper() == linhas[0]:
        linhas = linhas[1:]
    d = " ".join(linhas)
    d += f"\n\nCódigo {x['codigoAR']} · Angelo Rabêlo, Corretor CRECI-PE 9560 · WhatsApp (81) 99383-7490"
    return d[:9000]


def main():
    os.makedirs(IMG, exist_ok=True)
    hp = os.path.join(IMG, "hashes.json")
    primeira = not os.path.exists(hp)
    hashes = {} if primeira else json.load(open(hp))
    lista = [x for x in imoveis() if x.get("codigoAR") and x["codigoAR"] not in FORA]
    tmp = tempfile.mkdtemp()
    feitas, sem_foto = [], []
    for x in lista:
        ar, sig = x["codigoAR"], assinatura(x)
        existe = os.path.exists(os.path.join(IMG, ar + ".jpg"))
        if existe and (hashes.get(ar) == sig or (primeira and ar not in hashes)):
            hashes[ar] = sig  # 1ª execução: as miniaturas atuais valem como base
            continue
        f = capa(x, tmp)
        if not f:
            sem_foto.append(ar); continue
        try:
            render(x, f, tmp); hashes[ar] = sig; feitas.append(ar)
        except Exception as e:
            sem_foto.append(f"{ar} ({e})")
    json.dump(hashes, open(hp, "w"), indent=0, sort_keys=True)

    extra_p = os.path.join(SITE, "catalogo", "precos-extra.json")
    extra = json.load(open(extra_p)) if os.path.exists(extra_p) else {}
    rows, fora = [], sorted(FORA)
    for x in lista:
        ar = x["codigoAR"]
        if (x.get("status") or "Disponível") != "Disponível":
            fora.append(ar + " (status)"); continue
        valor = x.get("venda") or x.get("aluguel") or x.get("diaria") or extra.get(ar)
        if not valor:
            fora.append(ar + " (sob consulta)"); continue
        if not os.path.exists(os.path.join(IMG, ar + ".jpg")):
            fora.append(ar + " (sem miniatura)"); continue
        fotos = [f for f in (x.get("fotos") or []) if re.search(r"\.(jpe?g|png)(\?|$)", f, re.I)][:5]
        if os.path.exists(os.path.join(SITE, "assets", "imoveis", "og", ar + ".jpg")):
            fotos.insert(0, f"{BASE}/assets/imoveis/og/{ar}.jpg")
        rows.append({
            "id": ar, "title": f"{ar} · {x['titulo']}"[:150], "description": descricao(x),
            "availability": "in stock", "condition": "new", "price": f"{float(valor):.2f} BRL",
            "link": f"{BASE}/imovel/{ar}/?utm_source=whatsapp&utm_medium=catalogo&utm_campaign={ar}",
            # ?v= muda quando a miniatura é refeita, para a Meta baixar a imagem nova
            "image_link": f"{BASE}/catalogo/img/{ar}.jpg?v={hashes.get(ar, '1')}",
            "additional_image_link": ",".join(fotos), "brand": "Rabêlo Imóveis",
            "custom_label_0": x.get("tipo") or "", "custom_label_1": x.get("cidade") or "",
            "custom_label_2": x.get("finalidade") or "",
        })
    with open(os.path.join(SITE, "catalogo", "meta-feed.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f"Miniaturas novas/refeitas: {len(feitas)} {' '.join(feitas)} | sem foto: {sem_foto}")
    print(f"Feed: {len(rows)} itens | fora: {fora}")


if __name__ == "__main__":
    main()
