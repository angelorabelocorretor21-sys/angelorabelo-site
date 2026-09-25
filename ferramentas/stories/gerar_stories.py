#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gerar_stories.py — cria a arte de Story (1080x1920, JPEG) de cada imóvel do site.

Saída: assets/stories/AR-XXXX.jpg (servida em https://www.angelorabeloimoveis.com.br/assets/stories/AR-XXXX.jpg,
usada pela tarefa diária que publica 1 Story por dia via Windsor.ai create_story).

Roda no Mac do Angelo (só biblioteca padrão + Google Chrome em modo headless + sips):
    cd ~/.rabelo-sync/angelorabelo-site && python3 ferramentas/stories/gerar_stories.py          # só os que faltam
    python3 ferramentas/stories/gerar_stories.py --todos                                        # refaz todos
    python3 ferramentas/stories/gerar_stories.py AR-0125 AR-0126                                # só estes
Também roda em Linux com Playwright (usado para testar): --playwright
"""
import html, json, os, re, subprocess, sys, tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SAIDA = os.path.join(RAIZ, "assets", "stories")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "template.html")


def imoveis():
    h = open(os.path.join(RAIZ, "index.html"), encoding="utf-8").read()
    i = h.index("const IMOVEIS")
    s = h.index("[", i)
    arr, _ = json.JSONDecoder().raw_decode(h[s:])
    return arr


def brl(n):
    return "R$ " + f"{int(round(n)):,}".replace(",", ".")


def preco(i):
    if i.get("venda"):
        return brl(i["venda"])
    if i.get("aluguel"):
        return brl(i["aluguel"]) + "<small>/mês</small>"
    if i.get("diaria"):
        return brl(i["diaria"]) + "<small>/diária</small>"
    return "Consulte"


def feats(i):
    f = []
    def pl(n, s, p): return f"{n} {s if int(n) == 1 else p}"
    if i.get("quartos"): f.append(pl(i["quartos"], "quarto", "quartos"))
    if i.get("suites"): f.append(pl(i["suites"], "suíte", "suítes"))
    if i.get("vagas"): f.append(pl(i["vagas"], "vaga", "vagas"))
    a = i.get("areaTotal") or i.get("areaUtil")
    if a:
        a = float(a)
        f.append(("%s ha" % f"{a/10000:.1f}".replace(".", ",").replace(",0", "")) if a >= 20000 else f"{int(a):,} m²".replace(",", "."))
    return " · ".join(f[:4])


def pagina(i, capa_url):
    t = open(TEMPLATE, encoding="utf-8").read()
    fin = (i.get("finalidade") or "Venda").split(",")[0].strip()
    loc = " · ".join(x for x in [i.get("bairro"), i.get("cidade")] if x)
    rep = {
        "{{CAPA}}": capa_url,
        "{{CODIGO}}": i["codigoAR"],
        "{{TITULO}}": html.escape(i.get("titulo") or ""),
        "{{LOCAL}}": html.escape(loc),
        "{{PRECO}}": preco(i),
        "{{FEATS}}": html.escape(feats(i)),
        "{{FINALIDADE}}": html.escape("À " + fin.upper() if fin.lower() in ("venda",) else fin.upper()),
    }
    for k, v in rep.items():
        t = t.replace(k, v)
    return t


def capa_local(i):
    p = os.path.join(RAIZ, "assets", "imoveis", i["codigoAR"] + ".jpg")
    return p if os.path.exists(p) else None


def render_chrome(html_path, png_path):
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
                    "--window-size=1080,1920", "--virtual-time-budget=6000", "--allow-file-access-from-files",
                    "--screenshot=" + png_path, "file://" + html_path], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90)


def para_jpeg(png, jpg):
    if sys.platform == "darwin":
        subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "82", png, "--out", jpg],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        from PIL import Image
        Image.open(png).convert("RGB").save(jpg, "JPEG", quality=82, optimize=True)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    todos = "--todos" in sys.argv
    usar_pw = "--playwright" in sys.argv
    os.makedirs(SAIDA, exist_ok=True)
    lista = imoveis()
    if args:
        lista = [i for i in lista if i["codigoAR"] in args]
    feitos, pulados = [], []
    tmp = tempfile.mkdtemp()
    pw = None
    if usar_pw:
        from playwright.sync_api import sync_playwright
        pw = sync_playwright().start()
        nav = pw.chromium.launch(executable_path=os.environ.get("PW_CHROMIUM") or None)
        pg = nav.new_page(viewport={"width": 1080, "height": 1920})
    for i in lista:
        cod = i["codigoAR"]
        destino = os.path.join(SAIDA, cod + ".jpg")
        if os.path.exists(destino) and not todos and not args:
            continue
        capa = capa_local(i)
        if not capa:
            pulados.append(cod + " (sem capa local em assets/imoveis)")
            continue
        hp = os.path.join(tmp, cod + ".html")
        open(hp, "w", encoding="utf-8").write(pagina(i, "file://" + capa))
        png = os.path.join(tmp, cod + ".png")
        try:
            if pw:
                pg.goto("file://" + hp); pg.wait_for_timeout(400); pg.screenshot(path=png)
            else:
                render_chrome(hp, png)
            para_jpeg(png, destino)
            feitos.append(cod)
        except Exception as e:
            pulados.append(f"{cod} (erro: {e})")
    if pw:
        nav.close(); pw.stop()
    print("Stories gerados:", len(feitos), " ".join(feitos))
    if pulados:
        print("Pulados:", "; ".join(pulados))


if __name__ == "__main__":
    main()
