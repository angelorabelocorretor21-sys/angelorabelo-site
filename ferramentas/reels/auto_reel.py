#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auto_reel.py — Reel diário 100% automático (roda no GitHub Actions, sem Mac e sem Claude).

Escolhe o imóvel do dia (categoria do dia + rodízio de 45 dias), baixa as fotos, escolhe as
melhores pela nota de qualidade, monta o roteiro SÓ com dados do cadastro (index.html) e chama o
gerar_reel.py. Se o QC recusar, tenta o próximo candidato (até 4).

Uso:
  python3 ferramentas/reels/auto_reel.py <historico.json> <pasta_saida> [vaga]
  vaga = 1 (padrão, Reel das 18h, categoria do dia) ou 2 (Reel das 20h, categoria complementar —
  sempre um imóvel diferente do Reel 1, porque o Reel 1 já entrou no historico.json de hoje).
Grava em <pasta_saida>: reel.mp4, story*.mp4, capa.jpg, legenda.txt, qc.json, roteiro.json,
contato.jpg, e <historico.json> atualizado. Imprime um JSON de resumo.
"""
import datetime, json, os, shutil, subprocess, sys
from zoneinfo import ZoneInfo

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import gerar_reel as G  # noqa: E402

HOJE = datetime.datetime.now(ZoneInfo("America/Recife")).date()
VAGA = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3].isdigit() else 1
# Vaga 2 usa a categoria de 3 dias à frente (ex.: Seg residencial + Qui rural) para variar o tipo de imóvel
DIA_CAT = (HOJE.weekday() + (3 if VAGA == 2 else 0)) % 7
DIAS_RODIZIO = 45
MIN_FOTOS = 7
FORMATOS = ["TOUR", "ESTILO_DE_VIDA", "LISTA", "CURIOSIDADE", "PRECO", "OPORTUNIDADE", "LOCALIZACAO", "INVESTIMENTO"]

# Ganchos sem números (números só viriam do cadastro). {c} = cidade
GANCHOS = {
    "urbano": ["Você moraria em um lugar assim?", "Olha o que está à venda em {c}", "Quanto você pagaria por este imóvel?",
               "Imagine chegar em casa e ver isso", "Este imóvel em {c} chama atenção", "Seu próximo endereço em {c}?",
               "Conheça este imóvel em {c}", "Um lar pensado para a família", "Repare nos detalhes deste imóvel",
               "Esse pode ser o seu novo lar", "Você não vai acreditar nesta vista", "Espera até ver por dentro",
               "Salve antes que alguém compre", "Tour rápido por este imóvel em {c}", "Morar bem em {c} é assim"],
    "rural": ["Esse pode ser o seu refúgio no campo", "Olha essa propriedade em {c}", "Já pensou em viver no campo?",
              "Terra boa à venda em {c}", "Seu refúgio no campo em {c}", "Imagine acordar com essa vista do campo",
              "Uma propriedade rural para conhecer", "Paz e espaço em {c}", "Oportunidade no campo em {c}",
              "Você trocaria a cidade por isso?", "Espera até ver o tamanho disso", "Salve antes que alguém compre",
              "O sonho de ter terra em {c}", "Tour pela propriedade em {c}"],
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
NEUTRAS = {"urbano": ["Repare em cada detalhe", "Imagine sua rotina aqui", "Cada ambiente conta"],
          "rural": ["Espaço para viver bem no campo", "Natureza por todos os lados", "Repare nesta paisagem"],
          "terreno": ["Espaço para o seu projeto", "Imagine o que construir aqui"],
          "comercial": ["Espaço para o seu negócio", "Imagine sua empresa aqui"]}
CTAS = ["Agende sua visita", "Me chame no WhatsApp", "Fale comigo e saiba mais"]
STORY_G = ["Você moraria aqui?", "Olha este imóvel", "Já conhecia este?", "Repare nesta vista"]
TAG_CIDADE = {"gravatá": ["#Gravata", "#ImoveisGravata"], "chã grande": ["#ChaGrande"], "bezerros": ["#Bezerros"],
              "pombos": ["#Pombos"], "recife": ["#Recife", "#ImoveisRecife"], "caruaru": ["#Caruaru"],
              "tamandaré": ["#Tamandare"], "sairé": ["#Saire"], "vitória de santo antão": ["#VitoriaDeSantoAntao"]}


def sem_acento(s):
    import unicodedata
    return "".join(ch for ch in unicodedata.normalize("NFD", s) if unicodedata.category(ch) != "Mn")


AGRESTE = ("gravatá", "bezerros", "chã grande", "pombos", "caruaru", "sairé", "garanhuns", "são caetano",
           "belo jardim", "santa cruz do capibaribe", "toritama", "taquaritinga do norte", "brejo da madre de deus",
           "agrestina", "cupira", "bonito", "camocim de são félix", "barra de guabiraba", "riacho das almas", "passira")
METRO = ("recife", "jaboatão dos guararapes", "olinda", "paulista", "camaragibe", "são lourenço da mata", "cabo de santo agostinho")
LITORAL = ("tamandaré", "ipojuca", "porto de galinhas", "sirinhaém", "barreiros", "são josé da coroa grande", "goiana", "itamaracá")


def regiao(im):
    """Região real da cidade (09/10/2026: #AgrestePernambucano só para cidades do Agreste)."""
    c = (im.get("cidade") or "").strip().lower()
    if c in AGRESTE: return ("Agreste", "#AgrestePernambucano")
    if c in METRO: return ("Região Metropolitana do Recife", "#GrandeRecife")
    if c in LITORAL: return ("Litoral de Pernambuco", "#LitoralPernambucano")
    if c: return ("Pernambuco", "#Pernambuco")
    return ("Pernambuco", "#Pernambuco")


def hashtags(im, cat):
    """8 a 12 hashtags (padrão v3 dos posts diários, 09/10/2026): específicas do imóvel primeiro
    (cidade, tipo, região), depois marca e as genéricas de alcance do nicho imobiliário."""
    cid = (im.get("cidade") or "").strip()
    tags = list(TAG_CIDADE.get(cid.lower(), ["#" + sem_acento(cid).replace(" ", "").replace("-", "")] if cid else []))
    t = (im.get("tipo") or "").lower() + " " + (im.get("titulo") or "").lower()
    if "fazenda" in t: tags.append("#FazendaAVenda")
    elif "sítio" in t or "sitio" in t: tags.append("#SitioAVenda")
    elif "chácara" in t or "chacara" in t: tags.append("#ChacaraAVenda")
    elif "haras" in t: tags.append("#Haras")
    elif cat == "terreno": tags.append("#TerrenoAVenda")
    elif "flat" in t: tags.append("#FlatAVenda")
    elif "apart" in t: tags.append("#ApartamentoAVenda")
    elif "condom" in t and "casa" in t: tags.append("#CasaEmCondominio")
    elif "condom" in t: tags.append("#ImovelEmCondominio")
    elif cat == "comercial": tags.append("#ImovelComercial")
    else: tags.append("#CasaAVenda")
    tags.append(regiao(im)[1])
    estilo = {"rural": "#VidaNoCampo", "urbano": "#CasaDosSonhos", "terreno": "#InvestimentoImobiliario",
              "comercial": "#InvestimentoImobiliario"}[cat]
    tags += ["#AngeloRabeloImoveis", "#RabeloImoveis", estilo, "#imoveis", "#corretordeimoveis",
             "#ImoveisPernambuco", "#mercadoimobiliario", "#oportunidade", "#CRECI9560"]
    out = []
    for x in tags:
        if x not in out and " " not in x:
            out.append(x)
    return out[:12]


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
    dia = DIA_CAT
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


VIRAL = {  # 1ª linha da legenda (padrão v3 dos posts diários): gancho forte em CAIXA ALTA
    "urbano": ["🚨 VOCÊ MORARIA AQUI? OLHA ESSE IMÓVEL EM {C}!", "🚨 ESSE IMÓVEL EM {C} VAI TE SURPREENDER!",
               "🔥 SALVA ESSE VÍDEO: OPORTUNIDADE EM {C}!", "✨ É ASSIM QUE SE MORA BEM EM {C}!",
               "🚨 ASSISTA ATÉ O FINAL E VEJA O PREÇO!", "🔥 IMÓVEL NOVO NA VITRINE EM {C}!"],
    "rural": ["🚨 JÁ PENSOU EM TER O SEU PEDAÇO DE CHÃO EM {C}?", "🌿 O REFÚGIO NO CAMPO QUE VOCÊ PROCURAVA!",
              "🔥 SALVA ESSE VÍDEO: PROPRIEDADE RURAL EM {C}!", "🚨 TERRA BOA À VENDA EM {C} — ASSISTA ATÉ O FINAL!",
              "✨ ESPAÇO, NATUREZA E PATRIMÔNIO EM {C}!", "🚨 VOCÊ TROCARIA A CIDADE POR ISSO?"],
    "terreno": ["🚨 SEU PROJETO COMEÇA AQUI, EM {C}!", "🔥 TERRENO À VENDA EM {C} — SALVA ESSE VÍDEO!",
                "✨ ONDE VOCÊ CONSTRUIRIA A SUA CASA?", "🚨 OPORTUNIDADE PARA CONSTRUIR OU INVESTIR EM {C}!"],
    "comercial": ["🚨 SEU NEGÓCIO MERECE ESTE ESPAÇO EM {C}!", "🔥 OPORTUNIDADE COMERCIAL EM {C}!",
                  "✨ PONTO ESTRATÉGICO À VENDA EM {C}!", "🚨 INVESTIDOR, OLHA ISSO EM {C}!"],
}
APRESENTA = {  # frase de contexto SEM fatos novos (só estilo de vida/uso) — completa o parágrafo
    "urbano": ["Um imóvel para viver com conforto, praticidade e a tranquilidade que a sua família merece.",
               "Para quem quer morar bem ou garantir um imóvel que é patrimônio de verdade.",
               "Cada ambiente foi pensado para o dia a dia ficar mais leve — vale ver o vídeo até o final."],
    "rural": ["Para quem sonha com espaço, natureza e um patrimônio sólido no campo.",
              "Uma propriedade para viver, produzir ou descansar longe da correria da cidade.",
              "Terra é o investimento que atravessa gerações — e esta merece a sua visita."],
    "terreno": ["Espaço pronto para tirar o seu projeto do papel, do jeito que você sempre imaginou.",
                "Uma boa escolha para construir ou investir com segurança."],
    "comercial": ["Uma oportunidade para quem quer crescer, investir ou abrir um negócio com visibilidade.",
                  "Espaço com potencial para o seu próximo empreendimento."],
}
FECHA = {
    "urbano": ["Imóveis assim não ficam muito tempo disponíveis — agende a sua visita.",
               "Salve este vídeo e envie para quem está procurando o próximo lar.",
               "Venha conhecer pessoalmente: as fotos não mostram tudo."],
    "rural": ["Propriedades assim são raras na região — agende a sua visita.",
              "Salve este vídeo e envie para quem sonha com a vida no campo.",
              "Venha caminhar pela propriedade e sentir a energia do lugar."],
    "terreno": ["Boas áreas como esta saem rápido — garanta a sua visita.", "Salve e envie para quem quer construir."],
    "comercial": ["Agende uma visita e avalie o potencial pessoalmente.", "Salve e envie para quem está investindo."],
}
CTA_LEG = ["👉✨ Quer ver por dentro? Toque no link da bio e digite {cod} — fotos completas e falo com você agora mesmo!",
           "👉✨ Gostou? Comente \"EU QUERO\" ou toque no link da bio e digite {cod} para ver tudo!",
           "👉✨ Me chama no WhatsApp ou toque no link da bio e digite {cod} — respondo rapidinho!"]
EMAIL = "contato@angelorabeloimoveis.com.br"  # o mesmo publicado no rodapé do site


def frases_descricao(im):
    """Frases do texto do cadastro (sem título, sem preço, sem assinatura, sem CTA) para o parágrafo."""
    import re as _re
    txt = im.get("descricao") or ""
    corpo = txt.split("\n— ")[0].split("\n—")[0]
    linhas = [ln.strip() for ln in corpo.splitlines()[1:] if ln.strip()]
    out = []
    for ln in linhas:
        if ln[:1] in ("•", "-", "▪", "✔") or ln.startswith(("💰", "📲", "📱", "🌐", "📍", "✅")):
            continue
        for fr in _re.split(r"(?<=[.!?])\s+", ln):
            f = G.limpa(fr).strip(" :")
            if len(f) < 25 or "R$" in f or f.upper() == f or f[:1].isdigit():
                continue
            if any(k in f.lower() for k in ("whatsapp", "agende", "fale comigo", "chama", "garanta", "visite", "link da bio")):
                continue
            out.append(f if f[-1] in ".!?" else f + ".")
    return out[:3]


def legenda_v3(im, cat, gancho_video, semente):
    cid = (im.get("cidade") or "").strip() or "Pernambuco"
    cod = im["codigoAR"]
    titulo = (im.get("titulo") or im.get("tipo") or "").strip()
    reg = regiao(im)[0]
    viral = VIRAL[cat][semente % len(VIRAL[cat])].format(C=cid.upper())
    par = frases_descricao(im)
    par.append(APRESENTA[cat][semente % len(APRESENTA[cat])])
    ficha = []
    tipo = (im.get("tipo") or "").strip()
    bairro = (im.get("bairro") or "").strip()
    ficha.append(f"🏠 {tipo or 'Imóvel'} em {bairro + ', ' if bairro and bairro.lower() not in (cid.lower(), 'centro') else ''}{cid}")
    q, su, b, v = G.num(im.get("quartos")), G.num(im.get("suites")), G.num(im.get("banheiros")), G.num(im.get("vagas"))
    if q: ficha.append(f"🛏️ {q} quarto" + ("s" if q > 1 else "") + (f" (sendo {su} suíte" + ("s" if su > 1 else "") + ")" if su else ""))
    elif su: ficha.append(f"🛏️ {su} suíte" + ("s" if su > 1 else ""))
    if b: ficha.append(f"🚿 {b} banheiro" + ("s" if b > 1 else ""))
    if v: ficha.append(f"🚗 {v} vaga" + ("s" if v > 1 else "") + " de garagem")
    au, at = G.area_txt(im.get("areaUtil")), G.area_txt(im.get("areaTotal"))
    if au and at and at != au: ficha.append(f"📐 {au} de área construída · {at} de área total")
    elif au or at: ficha.append(f"📐 {au or at} de área")
    preco = G.preco_txt(im)
    if preco: ficha.append(f"💰 {preco}")
    linhas = [viral, "", gancho_video, "", f"🏡 {titulo}", "", " ".join(par), "",
              CTA_LEG[semente % len(CTA_LEG)].format(cod=cod), "", "📋 FICHA DO IMÓVEL:"] + ficha + [
              "", FECHA[cat][semente % len(FECHA[cat])], "",
              "📲 Fale comigo agora mesmo:", f"💬 WhatsApp: {G.WHATS}", "🌐 Site: www.angelorabeloimoveis.com.br",
              f"📧 E-mail: {EMAIL}", "", f"— Angelo Rabêlo | Corretor CRECI-PE {G.CRECI} · Perito Avaliador",
              f"Rabêlo Imóveis · {cid} · {reg}"]
    return "\n".join(linhas)


def roteiro(im, hist, fotos_ok):
    cat = G.categoria(im)
    cid = (im.get("cidade") or "").strip() or "Pernambuco"
    usados_g = [h.get("gancho") for h in hist[-14:]]
    usados_f = [h.get("formato") for h in hist[-3:]]
    semente = HOJE.toordinal() + (7 if VAGA == 2 else 0)
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
    # 09/10/2026: as características (quartos, suítes, área…) vão juntas no cartão "FICHA DO IMÓVEL";
    # as frases de destaque usam os tópicos do texto do cadastro e chamadas neutras (sem fatos novos)
    destaques = [x for x in itens if len(x) <= 34][:3]
    if len(fch) < 2:
        destaques = (list(fch) + destaques)[:3] + [local]
        if len(destaques) < 2 and tipo: destaques.insert(0, tipo[:40])
    neutras = NEUTRAS[cat]
    destaques.append(neutras[semente % len(neutras)])
    destaques = destaques[:4]
    cta = CTAS[semente % len(CTAS)]
    # fotos (09/10/2026): as melhores por nota — abertas, claras, arrumadas; capa = melhor foto externa
    esc = G.selecionar(fotos_ok, 11 if formato == "TOUR" else 10)
    ordem = [r["indice"] for r in esc]
    return {
        "codigo": im["codigoAR"], "formato": formato, "gancho": gancho, "gancho_sub": tipo[:40] if tipo else "",
        "destaques": destaques, "desejo": DESEJO[cat][semente % len(DESEJO[cat])], "mostrar_preco": True,
        "cta": cta, "stories": {"gancho": STORY_G[semente % len(STORY_G)], "destaque": (fch[0] + " em " + cid) if fch else f"{tipo} em {cid}"[:45]},
        "fotos": ordem, "legenda": legenda_v3(im, cat, gancho, semente), "hashtags": hashtags(im, cat),
    }


def preparar_extras():
    """09/10/2026 (v4): no GitHub Actions, prepara sozinho o que o workflow antigo não faz —
    músicas por estilo (rural/urbano) e a IA de fotos (CLIP). Assim basta enviar os arquivos
    desta pasta; o .yml do workflow não precisa mudar. Se algo falhar, o Reel sai mesmo assim."""
    if not os.environ.get("GITHUB_ACTIONS"):
        return
    musicas = G.MUSICAS
    if not (os.path.isdir(os.path.join(musicas, "rural")) and os.listdir(os.path.join(musicas, "rural"))):
        try:
            subprocess.run([sys.executable, os.path.join(AQUI, "baixar_musicas.py"), musicas], timeout=600,
                           stdout=sys.stderr, stderr=sys.stderr)
        except Exception as e:
            print("músicas por estilo falharam:", e, file=sys.stderr)
    try:
        import torch, open_clip  # noqa: F401
    except Exception:
        try:
            pip = ["sudo", "-E", sys.executable, "-m", "pip", "install", "-q", "--break-system-packages"]
            subprocess.run(pip + ["torch", "torchvision", "--index-url", "https://download.pytorch.org/whl/cpu"],
                           timeout=900, stdout=sys.stderr, stderr=sys.stderr)
            subprocess.run(pip + ["open_clip_torch"], timeout=600, stdout=sys.stderr, stderr=sys.stderr)
            import importlib, site
            importlib.invalidate_caches()
            for d in site.getsitepackages():
                if d not in sys.path:
                    sys.path.append(d)
        except Exception as e:
            print("IA de fotos indisponível:", e, file=sys.stderr)


def main():
    hist_path, saida = sys.argv[1], sys.argv[2]
    preparar_extras()
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
        hist.append({"data": HOJE.isoformat(), "codigo": cod, "formato": R["formato"], "gancho": R["gancho"], "origem": "auto", "vaga": VAGA})
        json.dump(hist, open(hist_path, "w"), ensure_ascii=False, indent=1)
        print(json.dumps({"ok": True, "data": HOJE.isoformat(), "codigo": cod, "categoria_dia": NOMES_DIA[DIA_CAT], "vaga": VAGA,
                          "na_categoria": im in do_dia, "tentativas": tentativas}, ensure_ascii=False))
        return 0
    print(json.dumps({"ok": False, "data": HOJE.isoformat(), "vaga": VAGA, "tentativas": tentativas}, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    sys.exit(main())
