#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
baixar_musicas.py — trilhas livres de direitos (Mixkit) separadas pela "pegada" do imóvel.
Roda no GitHub Actions antes de gerar os Reels (09/10/2026, pedido do Angelo):
  - rural   → country / folk / violão acústico, só faixas de clima suave (relaxed, calm, peaceful, romantic…)
  - urbano  → lo-fi, chillout, house suave — moderno e urbano, também só faixas suaves
Grava em <pasta>/rural/*.mp3 e <pasta>/urbano/*.mp3 (até 14 por estilo, sorteadas por dia para variar).
Se o site do Mixkit mudar e nada for encontrado, o gerar_reel.py usa as músicas antigas da pasta principal.

Uso: python3 baixar_musicas.py <pasta_musicas>
"""
import datetime, os, random, re, subprocess, sys, urllib.request

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
BASE = "https://mixkit.co/free-stock-music/"
ESTILOS = {
    "rural": ["country/", "tag/country/", "folk/", "instrument/acoustic-guitar/", "discover/acoustic/", "tag/farm/"],
    "urbano": ["lo-fi-beats/", "chillout/", "house/", "tag/urban/", "tag/city/", "tag/modern/"],
}
SUAVES = ["mood/relaxed/", "mood/calm/", "mood/peaceful/", "mood/romantic/", "mood/dreamy/", "mood/reflective/",
          "mood/positive/", "mood/hopeful/", "mood/friendly/", "mood/carefree/"]
AGITADAS = ["mood/aggressive/", "mood/epic/", "mood/scary/", "mood/humorous/", "mood/dark/", "mood/tense/"]
POR_ESTILO = 14
MIN_SEG = 34  # o Reel tem ~31 s


def get(url):
    try:
        return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25).read().decode("utf-8", "ignore")
    except Exception:
        return ""


def ids(url, paginas=4):
    """IDs de faixas citados na página (o link do mp3 é assets.mixkit.co/music/<id>/<id>.mp3,
    e as prévias costumam ser .../music/preview/mixkit-nome-<id>.mp3)."""
    achados = []
    for p in range(1, paginas + 1):
        h = get(url + ("" if p == 1 else f"?page={p}"))
        if not h:
            break
        novos = re.findall(r"mixkit\.co/music/(\d+)/\d+\.mp3", h)
        novos += re.findall(r"mixkit\.co/music/preview/[^\"'\s>]*?-(\d+)\.mp3", h)
        novos += re.findall(r"mixkit\.co/music/[^\"'\s>]*?-(\d+)\.mp3", h)
        if not novos:  # links das páginas de cada faixa: /free-stock-music/<nome>-<id>/
            novos = re.findall(r'href="(?:https://mixkit\.co)?/free-stock-music/[a-z0-9-]+-(\d{2,5})/"', h)
        if not novos:
            break
        for n in novos:
            if n not in achados:
                achados.append(n)
    return achados


def duracao(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def main():
    pasta = sys.argv[1]
    suaves, agitadas = set(), set()
    for m in SUAVES:
        suaves.update(ids(BASE + m, paginas=9))
    for m in AGITADAS:
        agitadas.update(ids(BASE + m, paginas=4))
    rnd = random.Random(datetime.date.today().toordinal())
    resumo = {}
    for estilo, paginas in ESTILOS.items():
        todos = []
        for pg in paginas:
            for n in ids(BASE + pg):
                if n not in todos:
                    todos.append(n)
        calmos = [n for n in todos if n in suaves and n not in agitadas]
        lista = calmos if len(calmos) >= 6 else [n for n in todos if n not in agitadas] or todos
        rnd.shuffle(lista)
        destino = os.path.join(pasta, estilo)
        os.makedirs(destino, exist_ok=True)
        ok = 0
        for n in lista:
            if ok >= POR_ESTILO:
                break
            f = os.path.join(destino, f"mixkit-{n}.mp3")
            try:
                data = urllib.request.urlopen(urllib.request.Request(f"https://assets.mixkit.co/music/{n}/{n}.mp3", headers=UA), timeout=40).read()
                open(f, "wb").write(data)
            except Exception:
                continue
            if os.path.getsize(f) < 150_000 or duracao(f) < MIN_SEG:
                os.remove(f)
                continue
            ok += 1
        resumo[estilo] = {"encontradas": len(todos), "suaves": len(calmos), "baixadas": ok}
    print(resumo)


if __name__ == "__main__":
    main()
