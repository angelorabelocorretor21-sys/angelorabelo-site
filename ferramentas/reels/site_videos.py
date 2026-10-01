#!/usr/bin/env python3
"""Copia os Reels para o site (assets/reels/).

Para cada vídeo recebido: comprime para 720x1280 (H.264, ~2-4 MB), tira uma capa JPG
e atualiza assets/reels/reels.json — a lista que o site lê (assets/reels.js).
Um vídeo por imóvel: um Reel novo do mesmo código substitui o anterior.

Uso:
  site_videos.py --pasta <dir com reel.mp4 e resultado.json> [--pasta ...]
  site_videos.py --extra "AR-0060 2026-09-25 https://.../reel.mp4" [--extra ...]
"""
import argparse, json, os, re, subprocess, sys, tempfile, urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DESTINO = os.path.join(RAIZ, "assets", "reels")
LISTA = os.path.join(DESTINO, "reels.json")
MAXIMO = 150  # guarda no máximo este número de vídeos (os mais antigos saem)
COD = re.compile(r"^AR-\d{4}$")
DATA = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def ler_lista():
    try:
        with open(LISTA, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(" ".join(cmd[:3]) + ": " + r.stderr[-400:])
    return r.stdout


def converter(origem, codigo):
    os.makedirs(DESTINO, exist_ok=True)
    mp4 = os.path.join(DESTINO, codigo + ".mp4")
    jpg = os.path.join(DESTINO, codigo + ".jpg")
    tmp = mp4 + ".tmp.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", origem,
         "-vf", "scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2,fps=30",
         "-c:v", "libx264", "-preset", "slow", "-crf", "28", "-profile:v", "high", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "96k", "-ac", "2", "-movflags", "+faststart", tmp])
    os.replace(tmp, mp4)
    run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "1.2", "-i", mp4, "-frames:v", "1",
         "-vf", "scale=540:-2", "-q:v", "5", jpg])
    dur = float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", mp4]).strip() or 0)
    return round(dur, 1), os.path.getsize(mp4)


def adicionar(lista, codigo, data, origem):
    if not COD.match(codigo or "") or not DATA.match(data or ""):
        print(f"ignorado (código/data inválidos): {codigo} {data}")
        return False
    atual = next((x for x in lista if x["codigo"] == codigo), None)
    if atual and atual.get("data", "") >= data:
        print(f"{codigo}: já está no site (Reel de {atual['data']})")
        return False
    dur, tam = converter(origem, codigo)
    lista[:] = [x for x in lista if x["codigo"] != codigo]
    lista.append({"codigo": codigo, "data": data, "video": f"/assets/reels/{codigo}.mp4",
                  "capa": f"/assets/reels/{codigo}.jpg", "duracao": dur})
    print(f"{codigo}: Reel de {data} adicionado ({dur}s, {tam/1e6:.1f} MB)")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pasta", action="append", default=[])
    ap.add_argument("--extra", action="append", default=[])
    a = ap.parse_args()
    lista = ler_lista()
    mudou = False
    for p in a.pasta:
        try:
            r = json.load(open(os.path.join(p, "resultado.json")))
            video = os.path.join(p, "reel.mp4")
            if r.get("ok") and os.path.exists(video):
                mudou |= adicionar(lista, r.get("codigo"), r.get("data"), video)
            else:
                print(f"{p}: sem Reel pronto")
        except Exception as e:
            print(f"{p}: {e}")
    for linha in a.extra:
        for item in re.split(r"[\n;]+", linha):
            partes = item.split()
            if len(partes) != 3:
                continue
            codigo, data, url = partes
            if not url.startswith("https://"):
                print(f"ignorado (link inválido): {item}")
                continue
            try:
                with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as t:
                    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                    t.write(urllib.request.urlopen(req, timeout=120).read())
                mudou |= adicionar(lista, codigo, data, t.name)
                os.unlink(t.name)
            except Exception as e:
                print(f"{codigo}: falhou ({e})")
    lista.sort(key=lambda x: (x["data"], x["codigo"]), reverse=True)
    for velho in lista[MAXIMO:]:
        for ext in (".mp4", ".jpg"):
            try:
                os.remove(os.path.join(DESTINO, velho["codigo"] + ext))
            except FileNotFoundError:
                pass
        mudou = True
    lista = lista[:MAXIMO]
    if mudou or not os.path.exists(LISTA):
        os.makedirs(DESTINO, exist_ok=True)
        with open(LISTA, "w", encoding="utf-8") as f:
            json.dump(lista, f, ensure_ascii=False, indent=1)
    print(f"{len(lista)} vídeos no site")


if __name__ == "__main__":
    sys.exit(main())
