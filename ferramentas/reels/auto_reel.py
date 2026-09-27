#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auto_reel.py — Reel diário 100% automático (roda no GitHub Actions, sem Mac e sem Claude).

Escolhe o imóvel do dia (categoria do dia + rodízio de 45 dias), baixa as fotos, escolhe as
melhores pela nota de qualidade, monta o roteiro SÓ com dados do cadastro (index.html) e chama o
gerar_reel.py. Se o QC recusar, tenta o próximo candidato (até 4).

Uso:
  python3 ferramentas/reels/auto_reel.py <historico.json> <pasta_saida>
Grava em <pasta_saida>: reel.mp4, story*.mp4, capa.jpg, legenda.txt, qc.json, roteiro.json,
contato.jpg, e <historico.json> atualizado. Imprime um JSON de resumo.
"""
import datetime, json, os, shutil, subprocess, sys
from zoneinfo import ZoneInfo

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import gerar_reel as G  # noqa: E402

HOJE = datetime.datetime.now(ZoneInfo("America/Recife")).date()
DIAS_RODIZIO = 45
MIN_FOTOS = 7
FORMATOS = ["TOUR", "ESTILO_DE_VIDA", "LISTA", "CURIOSIDADE", "PRECO", "OPORTUNIDADE", "LOCALIZACAO", "INVESTIMENTO"]

# Ganchos sem números (números só viriam do cadastro). {c} = cidade
GANCHOS = {
    "urbano": ["Você moraria em um lugar assim?", "Olha o que está à venda em {c}", "Quanto você pagaria por este imóvel?",
               "Imagine chegar em casa e ver isso", "Este imóvel em {c} chama atenção", "Seu próximo endereço em {c}?",
               "Conheça este imóvel em {c}", "Um lar pensado para a família", "Repare nos detalhes deste imóvel",
               "Esse pode ser o seu novo lar"],
    "rural": ["Esse pode ser o seu refúgio no campo", "Olha essa propriedade em {c}", "Já pensou em viver no campo?",
              "Terra boa à venda em {c}", "Seu refúgio no Agreste", "Imagine acordar com essa vista do campo",
              "Uma propriedade rural para conhecer", "Paz e espaço em {c}", "Oportunidade no campo em {c}",
              "Você trocaria a cidade por isso?"],
    "terreno": ["Um terreno para realizar seu projeto", "Oportunidade em {c}", "Construa do seu jeito em {c}",
                "Onde você construiria sua casa?", "Olha esse terreno em {c}", "Investir em terra é seguro?",
                "Seu projeto começa aqui", "Oportunidade para investir em {c}"],
    "comercial": ["Um ponto para o seu negócio em {c}", "Oportunidade comercial em {c}", "Seu negócio merece este espaço",
                  "Olha este imóvel comercial em {c}", "Investimento com potencial em {c}"],
}
DESEJO = {"urbano": ["Imagine sua família aqui", "Imagine seus dias aqui", "Conforto para viver bem"],
          "rural": ["Imagine seus fins de semana aqui", "Tranquilidade longe da cidade", "Imagine sua vida no campo"],
          "terreno": ["Imagine seu projeto aqui", "Espaço para realizar planos"],
          "comercial": ["Imagine seu negócio aqui", "Espaço para crescer"]}
CTAS = ["Agende sua visita", "Me chame no WhatsApp", "Fale comigo e saiba mais"]
STORY_G = ["Você moraria aqui?", "Olha este imóvel", "Já conhecia este?", "Repare nesta vista"]
TAG_CIDADE = {"gravatá": ["#Gravata", "#ImoveisGravata"], "chã grande": ["#ChaGrande"], "bezerros": ["#Bezerros"],
              "pombos": ["#Pombos"], "recife": ["#Recife", "#ImoveisRecife"], "caruaru": ["#Caruaru"],
              "tamandaré": ["#Tamandare"], "sairé": ["#Saire"], "vitória de santo antão": ["#VitoriaDeSantoAntao"]}


def sem_acento(s):
    import unicodedata
    return "".join(ch for ch in unicodedata.normalize("NFD", s) if unicodedata.category(ch) != "Mn")


def hashtags(im, cat):
    cid = (im.get("cidade") or "").strip()
    tags = list(TAG_CIDADE.get(cid.lower(), ["#" + sem_acento(cid).replace(" ", "")] if cid else []))
    t = (im.get("tipo") or "").lower() + " " + (im.get("titulo") or "").lower()
    if "fazenda" in t: tags.append("#FazendaAVenda")
    elif "sítio" in t or "sitio" in t: tags.append("#SitioAVenda")
    elif "chácara" in t or "chacara" in t: tags.append("#ChacaraAVenda")
    elif "haras" in t: tags.append("#Haras")
    elif cat == "terreno": tags.append("#TerrenoAVenda")
    elif "apart" in t: tags.append("#ApartamentoAVenda")
    elif "condom" in t: tags.append("#CasaEmCondominio")
    elif cat == "comercial": tags.append("#ImovelComercial")
    else: tags.append("#CasaAVenda")
    tags += ["#AgrestePernambucano", "#ImoveisPernambuco", "#AngeloRabeloImoveis"]
    out = []
    for x in tags:
        if x not in out and " " not in x:
            out.append(x)
    return out[:8]


def valor(im):
    return im.get("venda") or im.get("aluguel") or im.get("diaria") or 0


def categoria_do_dia(im, dia):
    cat, v = G.categoria(im), valor(im)
    t = (im.get("tipo") or "").lower() + " " + (im.get("titulo") or "").lower()
    cid = (im.get("cidade") or "").lower()
    if dia == 0: return cat == "urbano" and 0 < v <= 1_000_000
    if dia == 1: return cat == "urbano" and v >= 1_500_000
    if dia == 2: return cat in ("terreno", "comercial") or (cat == "urbano" and 0 < v <= 600_000)
    if dia == 3: return cat == "rural"
    if dia == 5: return ("chácara" in t or "chacara" in t or "sítio" in t or "sitio" in t or "condom" in t) and \
        any(c in cid for c in ("gravatá", "chã grande"))
    return True  # sex/dom: qualquer um (desempate decide)


NOMES_DIA = ["Seg residencial", "Ter alto padrão", "Qua investimento/oportunidade", "Qui rural",
             "Sex potencial comercial", "Sáb lazer/fim de semana", "Dom estilo de vida"]


def candidatos(hist):
    limite = HOJE - datetime.timedelta(days=DIAS_RODIZIO)
    recentes = {h["codigo"] for h in hist if datetime.date.fromisoformat(h["data"]) >= limite}
    ja = {h["codigo"] for h in hist}
    base = []
    for im in G.imoveis():
        c = im.get("codigoAR")
        if not c or c in G.EXCLUIDOS or c in G.SUSPEITOS or c in recentes:
            continue
        if len(im.get("fotos") or []) < MIN_FOTOS or not valor(im):
            continue
        base.append(im)
    dia = HOJE.weekday()
    do_dia = [im for im in base if categoria_do_dia(im, dia)]
    def chave(im):
        n = int((im["codigoAR"].split("-")[1]) or 0)
        return (im["codigoAR"] in ja, -(G.completude(im) >= 4), -n)
    if dia in (4, 6):  # sex/dom: priorizar os de maior valor (fotos e apelo costumam ser melhores)
        chave = lambda im: (im["codigoAR"] in ja, -valor(im))  # noqa: E731
    do_dia.sort(key=chave)
    resto = sorted([im for im in base if im not in do_dia], key=chave)
    return do_dia, resto


def itens_descricao(im):
    """Itens em tópico ('•' ou '-') da descrição do cadastro — texto já escrito para o imóvel."""
    out = []
    for ln in (im.get("descricao") or "").splitlines():
        t = ln.strip()
        if t[:1] in ("•", "-", "▪", "✔") or t.startswith("✅"):
            t = G.limpa(t.lstrip("•-▪✔✅ ").strip())
            t = t[:1].upper() + t[1:]
            if 3 < len(t) <= 60 and "R$" not in t and "whats" not in t.lower():
                out.append(t)
    return out


def curto(txt, n=45):
    return txt if len(txt) <= n else None


def roteiro(im, hist, fotos_ok):
    cat = G.categoria(im)
    cid = (im.get("cidade") or "").strip() or "Pernambuco"
    usados_g = [h.get("gancho") for h in hist[-14:]]
    usados_f = [h.get("formato") for h in hist[-3:]]
    semente = HOJE.toordinal()
    ganchos = [g.format(c=cid) for g in GANCHOS[cat]]
    ganchos = [g for g in ganchos if curto(g) and g not in usados_g] or [g.format(c=cid) for g in GANCHOS[cat]]
    gancho = ganchos[semente % len(ganchos)]
    formatos = [f for f in FORMATOS if f not in usados_f]
    if cat in ("urbano", "rural"):
        formatos = [f for f in formatos if f != "INVESTIMENTO"] or formatos
    formato = formatos[semente % len(formatos)]
    fch = G.fichas(im)
    local = G.local_txt(im).replace(" · ", ", ")
    tipo = (im.get("tipo") or "").strip()
    itens = itens_descricao(im)
    if fch:  # não repetir o que as fichas já dizem
        itens = [x for x in itens if not any(k in x.lower() for k in ("quarto", "suíte", "suite", "vaga", "m²", "banheiro"))]
    destaques = list(fch[:3])
    destaques += [x for x in itens if len(x) <= 34][: max(0, 4 - len(destaques) - 1)]
    destaques.append(local)
    if len(destaques) < 2 and tipo: destaques.insert(0, tipo[:40])
    destaques = destaques[:4]
    preco = G.preco_txt(im)
    cta = CTAS[semente % len(CTAS)]
    titulo = (im.get("titulo") or tipo).strip()
    linhas = [gancho, "", f"🏡 {titulo}", f"📍 {local}", ""]
    ck = ([tipo] if tipo else []) + fch[:5]
    ck += [x for x in itens if x.lower() not in " ".join(ck).lower()][: max(0, 7 - len(ck))]
    linhas += [f"✅ {x}" for x in ck]
    linhas += ["", f"💰 {preco}", "", f"{cta}! Salve e envie para quem procura imóvel em {cid}.",
               f"📲 WhatsApp {G.WHATS}", "", f"— Angelo Rabêlo · Corretor CRECI-PE {G.CRECI} · Perito Avaliador"]
    # fotos: capa = melhor nota entre as boas; resto na ordem do cadastro
    boas = [r for r in fotos_ok if not r["duplicada"] and not r["pequena"]]
    capa = max(boas[:6], key=lambda r: r["nota"])  # entre as primeiras (fachada/externa costumam vir antes)
    resto = sorted([r for r in boas if r is not capa], key=lambda r: -r["nota"])[:9]
    resto.sort(key=lambda r: r["indice"])
    ordem = [capa["indice"]] + [r["indice"] for r in resto]
    return {
        "codigo": im["codigoAR"], "formato": formato, "gancho": gancho, "gancho_sub": tipo[:40] if tipo else "",
        "destaques": destaques, "desejo": DESEJO[cat][semente % len(DESEJO[cat])], "mostrar_preco": True,
        "cta": cta, "stories": {"gancho": STORY_G[semente % len(STORY_G)], "destaque": (fch[0] + " em " + cid) if fch else f"{tipo} em {cid}"[:45]},
        "fotos": ordem, "legenda": "\n".join(linhas), "hashtags": hashtags(im, cat),
    }


def main():
    hist_path, saida = sys.argv[1], sys.argv[2]
    hist = json.load(open(hist_path)) if os.path.exists(hist_path) else []
    os.makedirs(saida, exist_ok=True)
    do_dia, resto = candidatos(hist)
    tentativas = []
    for im in (do_dia + resto)[:8]:
        if len(tentativas) >= 4:
            break
        cod = im["codigoAR"]
        fotos = G.preparar_fotos(im)
        boas = [r for r in fotos if not r["duplicada"] and not r["pequena"]]
        pasta = os.path.join(G.CACHE, cod)
        json.dump(fotos, open(os.path.join(pasta, "fotos.json"), "w"), ensure_ascii=False)
        if len(boas) < MIN_FOTOS:
            tentativas.append({"codigo": cod, "motivo": f"só {len(boas)} fotos boas"})
            continue
        R = roteiro(im, hist, fotos)
        rp = os.path.join(saida, "roteiro.json")
        json.dump(R, open(rp, "w"), ensure_ascii=False, indent=1)
        p = subprocess.run([sys.executable, os.path.join(AQUI, "gerar_reel.py"), "gerar", rp], capture_output=True, text=True)
        out = os.path.join(G.SAIDA, f"{datetime.date.today().isoformat()}_{cod}")
        qcf = os.path.join(out, "qc.json")
        qc = json.load(open(qcf)) if os.path.exists(qcf) else {"aprovado_qc": False, "problemas": [p.stderr[-800:]]}
        if not qc.get("aprovado_qc"):
            tentativas.append({"codigo": cod, "motivo": "QC: " + "; ".join(qc.get("problemas") or [])[:300]})
            shutil.rmtree(out, ignore_errors=True)
            continue
        for f in os.listdir(out):
            shutil.copy(os.path.join(out, f), saida)
        G.contato(fotos, os.path.join(saida, "contato.jpg"))
        hist.append({"data": HOJE.isoformat(), "codigo": cod, "formato": R["formato"], "gancho": R["gancho"], "origem": "auto"})
        json.dump(hist, open(hist_path, "w"), ensure_ascii=False, indent=1)
        print(json.dumps({"ok": True, "data": HOJE.isoformat(), "codigo": cod, "categoria_dia": NOMES_DIA[HOJE.weekday()],
                          "na_categoria": im in do_dia, "tentativas": tentativas}, ensure_ascii=False))
        return 0
    print(json.dumps({"ok": False, "data": HOJE.isoformat(), "tentativas": tentativas}, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    sys.exit(main())
