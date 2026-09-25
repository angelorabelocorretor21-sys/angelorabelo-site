#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gerar_reel.py — Reel (1080x1920, 20–45 s) + 2 a 4 Stories em vídeo de UM imóvel do site,
a partir de um roteiro JSON escrito pelo Claude na tarefa das 18h.

Roda no Mac do Angelo (Python 3.9 + Pillow + ffmpeg em ~/bin/ffmpeg). Só usa dados reais do
array IMOVEIS do index.html do site — os textos do roteiro passam por uma checagem que recusa
qualquer número que não exista no cadastro do imóvel.

Uso:
  cd ~/.rabelo-sync/angelorabelo-site && git pull -q
  python3 ferramentas/reels/gerar_reel.py listar            # candidatos (JSON) para escolher o imóvel do dia
  python3 ferramentas/reels/gerar_reel.py fotos AR-0129     # baixa fotos, nota de qualidade, gera contato.jpg para olhar
  python3 ferramentas/reels/gerar_reel.py gerar roteiro.json  # renderiza Reel + Stories + legenda + qc.json

Saída: ~/.rabelo-sync/reels-saida/<AAAA-MM-DD>_<AR-XXXX>/
  reel.mp4, story1.mp4 … story4.mp4, capa.jpg, legenda.txt, qc.json

Formato do roteiro (todos os textos SEM emoji; números só se existirem no cadastro):
{
  "codigo": "AR-0129",
  "formato": "TOUR",                       # TOUR, CURIOSIDADE, PRECO, INVESTIMENTO, ESTILO_DE_VIDA,
                                           # LISTA, OPORTUNIDADE, ANTES_DE_COMPRAR, LOCALIZACAO, COMPARACAO
  "gancho": "Olha o que acabou de entrar à venda em Pombos",
  "gancho_sub": "Haras completo",          # opcional, linha menor abaixo do gancho
  "destaques": ["Haras completo", "Pombos - PE", "Pronto para receber"],   # 2 a 6 textos curtos, 1 por cena
  "desejo": "Imagine seus fins de semana aqui",
  "mostrar_preco": true,
  "cta": "Agende sua visita",
  "stories": {"gancho": "Você moraria aqui?", "destaque": "Haras completo em Pombos"},
  "fotos": [0, 3, 5, 7, 9, 12, 14, 18],    # opcional: 7 a 11 índices (do comando fotos) na ordem das cenas; 1ª = abertura, última = cena do preço
  "foto_preco": 3,                         # opcional: índice da foto da cena do preço
  "musica": "nome-do-arquivo.mp3",         # opcional; sem isso roda o rodízio da pasta de músicas
  "legenda": "texto da legenda SEM o bloco de link e SEM hashtags",
  "hashtags": ["#Pombos", "#Haras", "#ImoveisPernambuco", "#RabeloImoveis", "#CRECI9560"]
}
"""
import datetime, glob, hashlib, io, json, os, random, re, shutil, subprocess, sys, tempfile, urllib.request

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps, ImageStat

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(os.path.dirname(AQUI))
HOME = os.path.expanduser("~")
BASE = os.path.join(HOME, ".rabelo-sync")
CACHE = os.path.join(BASE, "reels-cache")
SAIDA = os.path.join(BASE, "reels-saida")
MUSICAS = os.path.join(BASE, "reels-musicas")
FFMPEG = os.environ.get("FFMPEG") or (os.path.join(HOME, "bin", "ffmpeg") if os.path.exists(os.path.join(HOME, "bin", "ffmpeg")) else "ffmpeg")

W, H, FPS = 1080, 1920, 30
XF = 0.45  # duração das transições

# Identidade (mesma das artes de Story do site)
ESCURO = (27, 22, 17)
DOURADO = (201, 162, 75)
DOURADO_CLARO = (226, 189, 106)
CREME = (244, 236, 222)
CINZA = (205, 191, 166)
WHATS = "(81) 99383-7490"
CRECI = "9560"
EXCLUIDOS = {"AR-0034", "AR-0108"}  # fazendas de Limoeiro — nunca divulgar
SUSPEITOS = {"AR-0096"}             # preço suspeito no cadastro

F_SERIF = os.path.join(AQUI, "fonts", "CormorantGaramond.ttf")
F_SANS = os.path.join(AQUI, "fonts", "Jost.ttf")


# ---------------------------------------------------------------- dados
def imoveis():
    h = open(os.path.join(RAIZ, "index.html"), encoding="utf-8").read()
    i = h.index("const IMOVEIS")
    s = h.index("[", i)
    arr, _ = json.JSONDecoder().raw_decode(h[s:])
    return arr


def achar(codigo):
    for x in imoveis():
        if x.get("codigoAR") == codigo:
            return x
    sys.exit(f"ERRO: {codigo} não está no site (index.html).")


def brl(n):
    return "R$ " + f"{int(round(n)):,}".replace(",", ".")


def preco_txt(im):
    if im.get("venda"):
        return brl(im["venda"])
    if im.get("aluguel"):
        return brl(im["aluguel"]) + "/mês"
    if im.get("diaria"):
        return brl(im["diaria"]) + "/diária"
    return ""


def num(v):
    if v in (None, "", 0):
        return None
    try:
        f = float(v)
        return int(f) if f == int(f) else f
    except Exception:
        return None


def area_txt(v):
    n = num(v)
    if not n:
        return None
    if n >= 10000:
        ha = n / 10000
        return (f"{ha:.1f}".rstrip("0").rstrip(".").replace(".", ",")) + " ha"
    return f"{int(n):,}".replace(",", ".") + " m²"


def fichas(im):
    """Características CONFIRMADAS no cadastro (só campos preenchidos)."""
    f = []
    q, s, b, v = num(im.get("quartos")), num(im.get("suites")), num(im.get("banheiros")), num(im.get("vagas"))
    if q: f.append(f"{q} quarto" + ("s" if q > 1 else ""))
    if s: f.append(f"{s} suíte" + ("s" if s > 1 else ""))
    if b and not s: f.append(f"{b} banheiro" + ("s" if b > 1 else ""))
    if v: f.append(f"{v} vaga" + ("s" if v > 1 else ""))
    au, at = area_txt(im.get("areaUtil")), area_txt(im.get("areaTotal"))
    if au: f.append(au + (" de área" if "ha" in au else " construídos"))
    if at and at != au: f.append(at + " de terreno" if "m²" in at else at + " de área")
    return f


def categoria(im):
    t = (im.get("tipo") or "").lower() + " " + (im.get("titulo") or "").lower()
    if any(k in t for k in ("fazenda", "sítio", "sitio", "chácara", "chacara", "haras", "granja", "rural")):
        return "rural"
    if any(k in t for k in ("lote", "terreno")):
        return "terreno"
    if any(k in t for k in ("comercial", "galpão", "galpao", "loja", "sala", "pousada", "hotel")):
        return "comercial"
    return "urbano"


def completude(im):
    campos = ["quartos", "suites", "banheiros", "vagas", "areaUtil", "areaTotal", "bairro"]
    return sum(1 for c in campos if num(im.get(c)) or (c == "bairro" and im.get("bairro")))


def local_txt(im):
    c, b = (im.get("cidade") or "").strip(), (im.get("bairro") or "").strip()
    if b and b.lower() not in ("centro", c.lower(), "zona rural"):
        return f"{b} · {c} - PE" if c else b
    return f"{c} - PE" if c else "Pernambuco"


def numeros_permitidos(im):
    """Todos os números que podem aparecer em textos (vêm do cadastro ou da marca)."""
    ok = set()
    def add(s):
        for d in re.findall(r"\d+", str(s)):
            ok.add(d.lstrip("0") or "0")
    for k in ("venda", "aluguel", "diaria"):
        if im.get(k):
            add(brl(im[k]))
            add(int(im[k]))
            n = im[k]
            # formas curtas: 1,85 milhão / 850 mil
            if n >= 1_000_000:
                add(f"{n/1_000_000:.2f}".rstrip("0").rstrip("."))
            if n >= 1000:
                add(int(n // 1000))
    for k in ("quartos", "suites", "banheiros", "vagas", "areaUtil", "areaTotal"):
        if num(im.get(k)):
            add(num(im[k]))
            a = area_txt(im[k])
            if a: add(a)
    add(im.get("codigoAR", "")); add(im.get("codigo", ""))
    add(im.get("titulo", "")); add(im.get("descricao", ""))
    add(WHATS); add(CRECI); add("24")  # "PE" não tem número; 24h permitido em "atendimento"? não usado
    ok.discard("24")
    return ok


def checa_numeros(textos, im):
    ok = numeros_permitidos(im)
    ruins = []
    for t in textos:
        for d in re.findall(r"\d+", t or ""):
            if (d.lstrip("0") or "0") not in ok:
                ruins.append(f"'{d}' em: {t}")
    return ruins


EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️‍]")


def limpa(t):
    return EMOJI.sub("", t or "").strip()


# ---------------------------------------------------------------- fotos
def baixar(url, destino):
    if os.path.exists(destino) and os.path.getsize(destino) > 1000:
        return True
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh) RabeloReels/1.0"})
        data = urllib.request.urlopen(req, timeout=30).read()
        Image.open(io.BytesIO(data)).convert("RGB").save(destino, "JPEG", quality=94)
        return True
    except Exception as e:
        print("  foto falhou:", url, e)
        return False


def dhash(im, n=8):
    g = im.convert("L").resize((n + 1, n), Image.BILINEAR)
    px = list(g.getdata())
    return sum(1 << i for i in range(n * n) if px[(i // n) * (n + 1) + i % n] > px[(i // n) * (n + 1) + i % n + 1])


def nota_foto(path):
    im = Image.open(path).convert("RGB")
    w, h = im.size
    t = im.copy(); t.thumbnail((500, 500))
    g = t.convert("L")
    nit = ImageStat.Stat(g.filter(ImageFilter.FIND_EDGES)).var[0]  # nitidez
    lum = ImageStat.Stat(g).mean[0]
    nota = min(nit / 2500, 1.0) * 55 + min(min(w, h) / 1000, 1.0) * 30 + (15 if 70 < lum < 200 else 5)
    return {"arquivo": path, "w": w, "h": h, "nitidez": round(nit), "luz": round(lum), "nota": round(nota, 1), "hash": dhash(t)}


def preparar_fotos(im, maximo=30):
    cod = im["codigoAR"]
    pasta = os.path.join(CACHE, cod)
    os.makedirs(pasta, exist_ok=True)
    urls = im.get("fotos") or ([im["foto"]] if im.get("foto") else [])
    res = []
    for i, u in enumerate(urls[:maximo]):
        dst = os.path.join(pasta, f"{i:02d}.jpg")
        if baixar(u, dst):
            info = nota_foto(dst)
            info["indice"] = i
            res.append(info)
    # marca quase-duplicadas
    vistos = []
    for r in res:
        r["duplicada"] = any(bin(r["hash"] ^ v).count("1") <= 6 for v in vistos)
        vistos.append(r["hash"])
        r["pequena"] = min(r["w"], r["h"]) < 600
    return res


def contato(fotos, destino):
    """Folha de contato numerada para o Claude olhar e escolher as fotos."""
    cols, tw, th = 5, 300, 220
    linhas = (len(fotos) + cols - 1) // cols
    folha = Image.new("RGB", (cols * tw, linhas * (th + 34)), (30, 30, 30))
    d = ImageDraw.Draw(folha)
    f = ImageFont.truetype(F_SANS, 22)
    for k, r in enumerate(fotos):
        t = ImageOps.fit(Image.open(r["arquivo"]).convert("RGB"), (tw - 6, th - 6))
        x, y = (k % cols) * tw, (k // cols) * (th + 34)
        folha.paste(t, (x + 3, y + 3))
        marca = f"#{r['indice']}  nota {r['nota']}" + ("  DUP" if r["duplicada"] else "") + ("  PEQ" if r["pequena"] else "")
        d.text((x + 6, y + th + 2), marca, font=f, fill=(255, 220, 120) if not (r["duplicada"] or r["pequena"]) else (255, 110, 110))
    folha.save(destino, "JPEG", quality=85)


def escolher_fotos(fotos, n, ordem=None):
    por_ind = {r["indice"]: r for r in fotos}
    if ordem:
        esc = [por_ind[i] for i in ordem if i in por_ind]
    else:
        boas = [r for r in fotos if not r["duplicada"] and not r["pequena"]]
        if len(boas) < 3:
            boas = [r for r in fotos if not r["duplicada"]] or fotos
        capa = boas[0]
        resto = sorted(boas[1:], key=lambda r: -r["nota"])[: n - 1]
        resto.sort(key=lambda r: r["indice"])  # mantém a ordem do cadastro (fachada → ambientes)
        esc = [capa] + resto
    return esc[:n]


# ---------------------------------------------------------------- rodapé antigo das fotos do RJWEB
def tem_rodape(im):
    """Fotos antigas do RJWEB trazem faixa verde com telefones antigos no rodapé
    e fotos da equipe no canto inferior direito. Detecta a faixa verde."""
    w, h = im.size
    verdes = tot = 0
    for fy in (0.965, 0.975, 0.985):
        for fx in (0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65):
            r, g, b = im.getpixel((int(w * fx), int(h * fy)))[:3]
            tot += 1
            if g > r + 50 and g > b + 35:
                verdes += 1
    return verdes >= tot * 0.6


def abrir_foto(path):
    """Abre a foto já sem o rodapé antigo. Retorna (imagem, limite_direito) — limite_direito é a
    fração da largura que o quadro pode mostrar sem pegar as fotos da equipe (1.0 = sem limite)."""
    im = Image.open(path).convert("RGB")
    if not tem_rodape(im):
        return im, 1.0
    w, h = im.size
    if w / h > 1.15:
        return im.crop((0, 0, w, int(h * 0.94))), 0.76
    # foto em pé: o quadro vertical mostra a largura toda — corta acima das fotos da equipe
    return im.crop((0, 0, w, int(h * 0.76))), 1.0


# ---------------------------------------------------------------- texto/arte
def fonte(path, tam, peso):
    f = ImageFont.truetype(path, tam)
    try:
        f.set_variation_by_name(peso)
    except Exception:
        pass
    return f


def quebra(d, txt, f, largura):
    palavras, linhas, atual = txt.split(), [], ""
    for p in palavras:
        teste = (atual + " " + p).strip()
        if d.textlength(teste, font=f) <= largura:
            atual = teste
        else:
            if atual: linhas.append(atual)
            atual = p
    if atual: linhas.append(atual)
    return linhas


def texto_ajustado(d, txt, path, peso, tam_max, tam_min, largura, max_linhas):
    tam = tam_max
    while tam >= tam_min:
        f = fonte(path, tam, peso)
        ls = quebra(d, txt, f, largura)
        if len(ls) <= max_linhas:
            return f, ls
        tam -= 4
    f = fonte(path, tam_min, peso)
    return f, quebra(d, txt, f, largura)[:max_linhas]


def gradiente(img, topo=0, base=0):
    g = Image.new("L", (1, H))
    for y in range(H):
        a = 0
        if topo and y < topo:
            a = int(215 * (1 - y / topo) ** 1.2)
        if base and y > H - base:
            a = max(a, int(235 * ((y - (H - base)) / base) ** 1.1))
        g.putpixel((0, y), a)
    sombra = Image.new("RGBA", (W, H), ESCURO + (0,))
    sombra.putalpha(g.resize((W, H)))
    img.alpha_composite(sombra)


def escreve(d, xy, linhas, f, cor, gap=1.08, centro=False, sombra=True):
    x, y = xy
    asc, desc = f.getmetrics()
    lh = int((asc + desc) * gap)
    for ln in linhas:
        lx = (W - d.textlength(ln, font=f)) / 2 if centro else x
        if sombra:
            d.text((lx + 3, y + 4), ln, font=f, fill=(0, 0, 0, 150))
        d.text((lx, y), ln, font=f, fill=cor)
        y += lh
    return y


def pilula(d, x, y, txt, f, borda=DOURADO, fundo=(27, 22, 17, 200), cor=(231, 199, 126)):
    tw = d.textlength(txt, font=f)
    asc, desc = f.getmetrics()
    h = asc + desc + 22
    d.rounded_rectangle((x, y, x + tw + 48, y + h), radius=h // 2, fill=fundo, outline=borda, width=3)
    d.text((x + 24, y + 9), txt, font=f, fill=cor)
    return x + tw + 48, y + h


def selo_marca(img):
    """Marca discreta no alto (não disputa com o imóvel)."""
    d = ImageDraw.Draw(img)
    f1 = fonte(F_SERIF, 38, "Bold")
    f2 = fonte(F_SANS, 17, "Medium")
    t1, t2 = "Angelo Rabêlo", "IMÓVEIS · CRECI 9560"
    w = max(d.textlength(t1, font=f1), d.textlength(t2, font=f2) * 1.25) + 44
    x0, y0 = W - 64 - w, 150
    d.rounded_rectangle((x0, y0, W - 64, y0 + 92), radius=14, fill=(27, 22, 17, 170))
    d.text((W - 64 - 22 - d.textlength(t1, font=f1), y0 + 10), t1, font=f1, fill=CREME)
    d.text((W - 64 - 22 - d.textlength(t2, font=f2) - 20, y0 + 58), " ".join(t2), font=f2, fill=(231, 210, 160))


def overlay(tipo, dados, im, destino):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    L = W - 144
    if tipo == "gancho":
        gradiente(img, topo=900, base=500)
        d = ImageDraw.Draw(img)
        f, ls = texto_ajustado(d, dados["texto"], F_SERIF, "Bold", 112, 70, L, 4)
        y = escreve(d, (72, 330), ls, f, (251, 245, 234), gap=1.02)
        if dados.get("sub"):
            fs, lss = texto_ajustado(d, dados["sub"], F_SANS, "Medium", 50, 36, L, 2)
            escreve(d, (72, y + 24), lss, fs, DOURADO_CLARO)
    elif tipo == "apresentacao":
        gradiente(img, base=1000)
        d = ImageDraw.Draw(img)
        fcod = fonte(F_SANS, 32, "SemiBold")
        pilula(d, 72, H - 900, "CÓD. " + im["codigoAR"], fcod)
        f, ls = texto_ajustado(d, dados["titulo"], F_SERIF, "Bold", 84, 58, L, 3)
        y = escreve(d, (72, H - 800), ls, f, (251, 245, 234), gap=1.0)
        fl = fonte(F_SANS, 40, "Regular")
        y = escreve(d, (72, y + 18), [dados["local"]], fl, CINZA)
        if dados.get("fichas"):
            ff, lf = texto_ajustado(d, "  ·  ".join(dados["fichas"]), F_SANS, "Medium", 38, 30, L, 2)
            escreve(d, (72, y + 10), lf, ff, (233, 220, 195))
        selo_marca(img)
    elif tipo == "destaque":
        gradiente(img, base=720)
        d = ImageDraw.Draw(img)
        d.rectangle((72, H - 560, 72 + 90, H - 554), fill=DOURADO)
        f, ls = texto_ajustado(d, dados["texto"], F_SERIF, "Bold", 92, 60, L, 3)
        escreve(d, (72, H - 525), ls, f, (251, 245, 234), gap=1.0)
    elif tipo == "desejo":
        gradiente(img, topo=700, base=600)
        d = ImageDraw.Draw(img)
        f, ls = texto_ajustado(d, dados["texto"], F_SERIF, "SemiBold", 96, 64, L, 3)
        escreve(d, (72, 360), ls, f, (251, 245, 234), gap=1.02, centro=True)
    elif tipo == "preco":
        gradiente(img, base=900)
        d = ImageDraw.Draw(img)
        fl = fonte(F_SANS, 40, "Medium")
        escreve(d, (72, H - 700), [dados.get("rotulo", "Valor")], fl, CINZA)
        fp, lp = texto_ajustado(d, dados["preco"], F_SERIF, "Bold", 150, 96, L, 1)
        escreve(d, (72, H - 640), lp, fp, DOURADO_CLARO, gap=1.0)
        fc = fonte(F_SANS, 34, "Medium")
        escreve(d, (72, H - 450), [local_txt(im)], fc, (233, 220, 195))
    img.save(destino)


def foto_angelo_circulo(diam):
    """Foto oficial do Angelo (assets/angelo-cartao.jpg, a mesma dos posts institucionais) em círculo com anel dourado."""
    src = Image.open(os.path.join(RAIZ, "assets", "angelo-cartao.jpg")).convert("RGB")
    lado = int(src.width * 0.80)
    x0 = max(0, min(src.width - lado, int(src.width * 0.53) - lado // 2))
    y0 = int(src.height * 0.27)
    src = src.crop((x0, y0, x0 + lado, y0 + lado)).resize((diam, diam), Image.LANCZOS)
    mask = Image.new("L", (diam * 4, diam * 4), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, diam * 4, diam * 4), fill=255)
    mask = mask.resize((diam, diam), Image.LANCZOS)
    anel = 14
    out = Image.new("RGBA", (diam + 2 * anel, diam + 2 * anel), (0, 0, 0, 0))
    ImageDraw.Draw(out).ellipse((0, 0, diam + 2 * anel - 1, diam + 2 * anel - 1), fill=DOURADO + (255,))
    out.paste(src, (anel, anel), mask)
    return out


def cartao_final(im, cta, destino, story=False):
    """Cartão final (modelo aprovado pelo Angelo em 25/09/2026): logo pequena no alto,
    foto do Angelo em destaque (como nos posts institucionais), nome, CRECI, CTA e WhatsApp."""
    img = Image.new("RGB", (W, H), ESCURO)
    d = ImageDraw.Draw(img)
    d.rectangle((48, 48, W - 48, H - 48), outline=(120, 97, 50), width=2)
    # logo PEQUENA em cartão branco (canto superior esquerdo), selo CRECI à direita
    logo = Image.open(os.path.join(AQUI, "logo.png")).convert("RGB")
    lw = 250
    logo = logo.resize((lw, int(logo.height * lw / logo.width)), Image.LANCZOS)
    d.rounded_rectangle((100, 120, 100 + lw + 40, 120 + logo.height + 36), radius=18, fill=(255, 255, 255))
    img.paste(logo, (120, 138))
    fcr = fonte(F_SANS, 28, "SemiBold")
    t = "CRECI-PE " + CRECI
    tw = d.textlength(t, font=fcr)
    yc = 120 + (logo.height + 36) // 2 - 30
    d.rounded_rectangle((W - 100 - tw - 56, yc, W - 100, yc + 60), radius=30, outline=(150, 122, 62), width=2)
    d.text((W - 100 - tw - 28, yc + 13), t, font=fcr, fill=(231, 210, 160))
    # foto do Angelo
    diam = 500
    foto = foto_angelo_circulo(diam)
    fy = 400
    img.paste(foto, ((W - foto.width) // 2, fy), foto)
    y = fy + foto.height + 40
    fn = fonte(F_SANS, 70, "SemiBold")  # Jost: o "ê" da Cormorant Bold sai com acento deslocado no Pillow
    y = escreve(d, (80, y), ["Angelo Rabêlo"], fn, CREME, centro=True, sombra=False)
    fs = fonte(F_SANS, 34, "Medium")
    y = escreve(d, (80, y + 6), ["Corretor de Imóveis · Perito Avaliador"], fs, DOURADO_CLARO, centro=True, sombra=False)
    d.rectangle((W // 2 - 50, y + 34, W // 2 + 50, y + 38), fill=DOURADO)
    y += 80
    f, ls = texto_ajustado(d, cta, F_SERIF, "Bold", 88, 64, W - 160, 2)
    y = escreve(d, (80, y), ls, f, CREME, centro=True, sombra=False)
    fw = fonte(F_SANS, 52, "SemiBold")
    y += 34
    tw = d.textlength("WhatsApp " + WHATS, font=fw)
    bx0 = (W - tw - 90) / 2
    d.rounded_rectangle((bx0, y, bx0 + tw + 90, y + 106), radius=53, fill=DOURADO)
    d.text((bx0 + 45, y + 21), "WhatsApp " + WHATS, font=fw, fill=ESCURO)
    y += 160
    fc = fonte(F_SANS, 40, "Medium")
    y = escreve(d, (80, y), ["Toque no link da bio e digite", "o código " + im["codigoAR"]], fc, (231, 210, 160), centro=True, sombra=False)
    fu = fonte(F_SANS, 32, "Regular")
    escreve(d, (80, y + 12), ["angelorabeloimoveis.com.br/" + im["codigoAR"]], fu, CINZA, centro=True, sombra=False)
    img.save(destino, "JPEG", quality=95)


# ---------------------------------------------------------------- vídeo
def ff(args, quiet=True):
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error"] + args
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg falhou: " + r.stderr[-1500:])


def cena(foto, dur, mov, sobre, destino, tmp):
    """Foto com movimento de câmera (pan/zoom suave) + texto que entra com fade."""
    src, lim = abrir_foto(foto)
    frames = int(round(dur * FPS))
    # base maior que o quadro para permitir movimento sem perder nitidez
    esc = max(W * 1.18 / src.width, H * 1.18 / src.height)
    horizontal = src.width / src.height > 1.15
    if horizontal and mov in ("pan_esq", "pan_dir"):
        esc = max(H * 1.06 / src.height, W / src.width)
    bw, bh = int(src.width * esc) // 2 * 2, int(src.height * esc) // 2 * 2
    base = os.path.join(tmp, os.path.basename(destino) + "_base.jpg")
    src.resize((bw, bh), Image.LANCZOS).save(base, "JPEG", quality=95)
    D = max(dur, 0.1)
    xmax = min(bw - W, int(bw * lim) - W)
    xmin = int((bw - W) * 0.08)
    if mov in ("pan_esq", "pan_dir") and xmax - xmin >= 80:
        x0, x1 = (xmax, xmin) if mov == "pan_esq" else (xmin, xmax)
        vf = f"crop={W}:{H}:x='{x0}+({x1 - x0})*t/{D}':y='({bh}-{H})/2'"
    else:
        # zoom suave: a base é redimensionada quadro a quadro e cortada no centro
        c = max(W / bw, H / bh)
        z0, z1 = (1.02, 1.15) if mov != "zoom_out" else (1.15, 1.02)
        kw = bw * c
        vf = (f"scale=w='trunc({kw:.2f}*({z0}+({z1 - z0:.3f})*t/{D})/2)*2':h=-2:eval=frame:flags=bicubic,"
              f"crop={W}:{H}")
    vf = vf + ",setsar=1,format=yuv420p"
    args = ["-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}", "-i", base]
    if sobre:
        args += ["-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}", "-i", sobre,
                 "-filter_complex", f"[0:v]{vf}[b];[1:v]format=rgba,fade=in:st=0.25:d=0.45:alpha=1[o];[b][o]overlay=0:0:format=auto,format=yuv420p[v]",
                 "-map", "[v]"]
    else:
        args += ["-vf", vf]
    args += ["-frames:v", str(frames), "-r", str(FPS), "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", destino]
    ff(args)


def cena_estatica(imagem, dur, destino):
    frames = int(round(dur * FPS))
    ff(["-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}", "-i", imagem,
        "-vf", f"scale={W}:{H},zoompan=z='min(1+0.0006*on,1.04)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={FPS},format=yuv420p",
        "-frames:v", str(frames), "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", destino])


TRANS = ["fade", "smoothleft", "fadeblack", "slideup", "circleopen", "smoothup", "fade", "wiperight"]


def juntar(partes, duracoes, destino, musica=None, semente=0):
    rnd = random.Random(semente)
    if len(partes) == 1:
        shutil.copy(partes[0], destino)
        total = duracoes[0]
    else:
        args = []
        for p in partes:
            args += ["-i", p]
        fc, atual, off = [], "[0:v]", 0.0
        for k in range(1, len(partes)):
            off += duracoes[k - 1] - XF
            t = rnd.choice(TRANS) if k < len(partes) - 1 else "fade"
            saida = f"[x{k}]" if k < len(partes) - 1 else "[v]"
            fc.append(f"{atual}[{k}:v]xfade=transition={t}:duration={XF}:offset={off:.3f}{saida}")
            atual = saida
        total = sum(duracoes) - XF * (len(partes) - 1)
        args += ["-filter_complex", ";".join(fc), "-map", "[v]"]
        sem_audio = destino + ".noaudio.mp4"
        ff(args + ["-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p", "-r", str(FPS), sem_audio])
        shutil.move(sem_audio, destino)
    if musica:
        com = destino + ".audio.mp4"
        ini = 0
        ff(["-i", destino, "-ss", str(ini), "-i", musica, "-filter_complex",
            f"[1:a]atrim=0:{total:.3f},asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.8,afade=t=out:st={max(total-1.8,0):.3f}:d=1.8,volume=0.85[a]",
            "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
            "-movflags", "+faststart", "-shortest", com])
        shutil.move(com, destino)
    else:
        com = destino + ".fs.mp4"
        # faixa de silêncio (o Instagram lida melhor com vídeo que tem trilha de áudio)
        ff(["-i", destino, "-f", "lavfi", "-t", f"{total:.3f}", "-i", "anullsrc=r=44100:cl=stereo",
            "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-shortest", "-movflags", "+faststart", com])
        shutil.move(com, destino)
    return total


def sonda(path):
    r = subprocess.run([FFMPEG, "-hide_banner", "-i", path], capture_output=True, text=True)
    txt = r.stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", txt)
    dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0
    m2 = re.search(r"Video: h264.*?, (\d+)x(\d+)", txt)
    res = (int(m2.group(1)), int(m2.group(2))) if m2 else (0, 0)
    return {"duracao": round(dur, 2), "resolucao": res, "audio": "Audio:" in txt, "tamanho_mb": round(os.path.getsize(path) / 1e6, 2)}


def escolher_musica(pedida, semente):
    if pedida:
        p = os.path.join(MUSICAS, pedida)
        if os.path.exists(p):
            return p
    fs = sorted(glob.glob(os.path.join(MUSICAS, "*.mp3")) + glob.glob(os.path.join(MUSICAS, "*.m4a")))
    if not fs:
        return None
    return fs[semente % len(fs)]


# ---------------------------------------------------------------- comandos
def cmd_listar():
    out = []
    for x in imoveis():
        c = x.get("codigoAR")
        if not c or c in EXCLUIDOS:
            continue
        out.append({"codigo": c, "titulo": x.get("titulo"), "tipo": x.get("tipo"), "categoria": categoria(x),
                    "cidade": x.get("cidade"), "preco": preco_txt(x), "fotos": len(x.get("fotos") or []),
                    "completude": completude(x), "fichas": fichas(x), "suspeito": c in SUSPEITOS})
    print(json.dumps(out, ensure_ascii=False))


def cmd_fotos(codigo):
    im = achar(codigo)
    fotos = preparar_fotos(im)
    pasta = os.path.join(CACHE, codigo)
    contato(fotos, os.path.join(pasta, "contato.jpg"))
    json.dump(fotos, open(os.path.join(pasta, "fotos.json"), "w"), ensure_ascii=False)
    print(json.dumps({"codigo": codigo, "baixadas": len(fotos), "contato": os.path.join(pasta, "contato.jpg"),
                      "fotos": [{k: r[k] for k in ("indice", "w", "h", "nota", "duplicada", "pequena")} for r in fotos]}, ensure_ascii=False))


def cmd_gerar(caminho_roteiro):
    R = json.load(open(caminho_roteiro, encoding="utf-8"))
    cod = R["codigo"]
    problemas, avisos = [], []
    if cod in EXCLUIDOS or cod in SUSPEITOS:
        problemas.append(f"{cod} está na lista de exclusão/suspeitos.")
    im = achar(cod)
    hoje = datetime.date.today().isoformat()
    out = os.path.join(SAIDA, f"{hoje}_{cod}")
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)
    tmp = tempfile.mkdtemp(prefix="reel_")
    semente = int(hashlib.md5((hoje + cod).encode()).hexdigest(), 16) % 10_000

    pasta = os.path.join(CACHE, cod)
    fj = os.path.join(pasta, "fotos.json")
    fotos = json.load(open(fj)) if os.path.exists(fj) else preparar_fotos(im)
    destaques = [limpa(t) for t in R.get("destaques", []) if limpa(t)][:6]
    if R.get("fotos"):
        n_fotos = min(len(R["fotos"]), 11)
    else:
        n_fotos = min(len(destaques) + 6, 11)
    esc = escolher_fotos(fotos, n_fotos, R.get("fotos"))
    if len(esc) < 4:
        problemas.append(f"Só {len(esc)} fotos utilizáveis (mínimo 4).")

    preco = preco_txt(im)
    mostrar_preco = bool(R.get("mostrar_preco", True)) and bool(preco)
    textos_tela = [limpa(R.get("gancho")), limpa(R.get("gancho_sub", "")), limpa(R.get("desejo")), limpa(R.get("cta"))] + destaques
    textos_tela += [limpa(v) for v in (R.get("stories") or {}).values()]
    ruins = checa_numeros(textos_tela, im)
    if ruins:
        problemas.append("Números que não existem no cadastro: " + "; ".join(ruins))
    if not limpa(R.get("gancho")):
        problemas.append("Roteiro sem gancho.")

    # ---------- Reel
    movs = ["zoom_in", "pan_dir", "zoom_out", "pan_esq"]
    partes, durs = [], []
    k = 0
    def add(foto, dur, tipo, dados, idx):
        nonlocal k
        sob = None
        if tipo:
            sob = os.path.join(tmp, f"ov{k}.png"); overlay(tipo, dados, im, sob)
        dst = os.path.join(tmp, f"c{k:02d}.mp4")
        cena(foto["arquivo"], dur, movs[idx % 4], sob, dst, tmp)
        partes.append(dst); durs.append(dur); k += 1

    fila = list(esc)
    add(fila.pop(0), 3.3, "gancho", {"texto": limpa(R["gancho"]), "sub": limpa(R.get("gancho_sub", ""))}, 0)
    if fila:
        add(fila.pop(0), 4.2, "apresentacao", {"titulo": limpa(im.get("titulo") or im.get("tipo")), "local": local_txt(im), "fichas": fichas(im)[:4]}, 1)
    reservas_fim = 2 if mostrar_preco else 1
    i = 2
    for t in destaques:
        if len(fila) <= reservas_fim:
            break
        add(fila.pop(0), 3.0, "destaque", {"texto": t}, i); i += 1
    while len(fila) > reservas_fim and sum(durs) < 22:
        add(fila.pop(0), 2.4, None, None, i); i += 1
    if fila:
        add(fila.pop(0), 3.6, "desejo", {"texto": limpa(R.get("desejo") or "Imagine você aqui")}, i); i += 1
    if mostrar_preco and fila:
        add(fila.pop(0) if not R.get("foto_preco") else next((r for r in esc if r["indice"] == R["foto_preco"]), fila.pop(0)), 3.4, "preco", {"preco": preco, "rotulo": "Valor de venda" if im.get("venda") else "Valor"}, i); i += 1
    fim = os.path.join(tmp, "final.jpg")
    cartao_final(im, limpa(R.get("cta") or "Agende sua visita"), fim)
    dfim = os.path.join(tmp, "cfinal.mp4")
    cena_estatica(fim, 4.2, dfim)
    partes.append(dfim); durs.append(4.2)

    musica = escolher_musica(R.get("musica"), semente)
    if not musica:
        avisos.append("Sem música na pasta ~/.rabelo-sync/reels-musicas — vídeo saiu sem trilha.")
    reel = os.path.join(out, "reel.mp4")
    juntar(partes, durs, reel, musica, semente)
    info_reel = sonda(reel)
    # capa = 1ª cena com o gancho
    capa = abrir_foto(esc[0]["arquivo"])[0]
    capa = ImageOps.fit(capa, (W, H)).convert("RGBA")
    capa.alpha_composite(Image.open(os.path.join(tmp, "ov0.png")))
    capa.convert("RGB").save(os.path.join(out, "capa.jpg"), "JPEG", quality=92)

    # ---------- Stories (2 a 4 vídeos curtos)
    st = R.get("stories") or {}
    story_defs = []
    story_defs.append(("gancho", {"texto": limpa(st.get("gancho") or R["gancho"]), "sub": local_txt(im)}, esc[0]))
    if len(esc) > 2:
        story_defs.append(("destaque", {"texto": limpa(st.get("destaque") or (destaques[0] if destaques else im.get("titulo")))}, esc[2 if len(esc) > 3 else 1]))
    if mostrar_preco and len(esc) > 3:
        story_defs.append(("preco", {"preco": preco, "rotulo": "Valor de venda" if im.get("venda") else "Valor"}, esc[-1]))
    stories = []
    for j, (tipo, dados, foto) in enumerate(story_defs, 1):
        sob = os.path.join(tmp, f"st{j}.png"); overlay(tipo, dados, im, sob)
        sv = os.path.join(tmp, f"s{j}.mp4"); cena(foto["arquivo"], 5.0, movs[j % 4], sob, sv, tmp)
        dst = os.path.join(out, f"story{j}.mp4"); juntar([sv], [5.0], dst, musica, semente + j)
        stories.append(dst)
    fim_s = os.path.join(tmp, "final_story.jpg")
    cartao_final(im, "Quer receber todas as informações?", fim_s, story=True)
    sv = os.path.join(tmp, "sfim.mp4"); cena_estatica(fim_s, 5.0, sv)
    dst = os.path.join(out, f"story{len(stories)+1}.mp4"); juntar([sv], [5.0], dst, musica, semente + 9)
    stories.append(dst)

    # ---------- legenda
    cidade = (im.get("cidade") or "").strip() or "Pernambuco"
    corpo = (R.get("legenda") or "").strip()
    if not corpo:
        problemas.append("Roteiro sem legenda.")
    bloco = (f"🔗 Todas as fotos e detalhes: angelorabeloimoveis.com.br/{cod}\n"
             f"👆 Ou toque no link da bio e digite o código {cod}\n"
             f"💾 Salve e envie para quem procura imóvel em {cidade}!")
    tags = " ".join(h if h.startswith("#") else "#" + h for h in (R.get("hashtags") or []) if " " not in h)
    legenda = f"{corpo}\n\n{bloco}\n\n{tags}".strip()
    ruins_leg = checa_numeros([corpo], im)
    if ruins_leg:
        problemas.append("Legenda com números fora do cadastro: " + "; ".join(ruins_leg))
    if WHATS not in corpo:
        avisos.append("Legenda sem o WhatsApp (81) 99383-7490 escrito.")
    if len(legenda) > 2200:
        problemas.append(f"Legenda com {len(legenda)} caracteres (máx. 2200).")
    if not (3 <= len(R.get("hashtags") or []) <= 12):
        avisos.append("Quantidade de hashtags fora de 3–12.")
    open(os.path.join(out, "legenda.txt"), "w", encoding="utf-8").write(legenda)

    # ---------- QC do vídeo
    if info_reel["resolucao"] != (W, H):
        problemas.append(f"Resolução do Reel {info_reel['resolucao']}")
    if not (20 <= info_reel["duracao"] <= 45):
        problemas.append(f"Duração do Reel {info_reel['duracao']} s (esperado 20–45 s)")
    info_st = [sonda(s) for s in stories]
    for s, inf in zip(stories, info_st):
        if not (3 <= inf["duracao"] <= 60) or inf["resolucao"] != (W, H):
            problemas.append(f"Story fora do padrão: {os.path.basename(s)} {inf}")

    qc = {"data": hoje, "codigo": cod, "codigo_rjweb": im.get("codigo"), "titulo": im.get("titulo"), "tipo": im.get("tipo"),
          "categoria": categoria(im), "cidade": im.get("cidade"), "preco": preco, "formato": R.get("formato"),
          "gancho": limpa(R.get("gancho")), "musica": os.path.basename(musica) if musica else None,
          "fotos_usadas": [r["indice"] for r in esc], "reel": info_reel, "stories": info_st,
          "arquivos": {"reel": reel, "capa": os.path.join(out, "capa.jpg"), "stories": stories, "legenda": os.path.join(out, "legenda.txt")},
          "problemas": problemas, "avisos": avisos, "aprovado_qc": not problemas}
    json.dump(qc, open(os.path.join(out, "qc.json"), "w"), ensure_ascii=False, indent=1)
    shutil.rmtree(tmp, ignore_errors=True)
    print(json.dumps(qc, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    c = sys.argv[1]
    if c == "listar":
        cmd_listar()
    elif c == "fotos":
        cmd_fotos(sys.argv[2])
    elif c == "gerar":
        cmd_gerar(sys.argv[2])
    else:
        sys.exit(__doc__)
