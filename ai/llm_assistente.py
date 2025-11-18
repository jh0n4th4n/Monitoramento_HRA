# ai/llm_assistente.py

from typing import Dict, List, Any, Optional


def _fmt_int(valor) -> str:
    try:
        v = int(round(float(valor)))
    except Exception:
        return "-"
    return f"{v:,}".replace(",", ".")


def _fmt_percent(valor) -> str:
    try:
        v = float(valor)
    except Exception:
        return "-"
    return f"{v:.1f}%"


def _top_keys_ordenados(d: Dict[str, Any], top_n: int = 5) -> List[tuple]:
    """
    Retorna [(chave, valor)] ordenado do maior para o menor.
    Ignora valores não numéricos.
    """
    pares_validos = []
    for k, v in d.items():
        try:
            num = float(v)
        except Exception:
            continue
        pares_validos.append((k, num))
    pares_validos.sort(key=lambda x: x[1], reverse=True)
    return pares_validos[:top_n]


# ================== BLOCO 1 – PANORAMA GERAL ==================

def _analisar_panorama(kpis: Dict[str, Any], nivel_detalhe: str) -> str:
    total = kpis.get("Total Solicitações", 0)
    concluidas = kpis.get("Concluídas", 0)
    taxa_conclusao = kpis.get("Taxa Conclusão (%)", 0)
    taxa_atraso = kpis.get("Taxa Atraso (%)", 0)

    texto = []
    texto.append("### 1. Panorama geral das solicitações\n")

    texto.append(
        f"- Volume total analisado: **{_fmt_int(total)}** solicitações registradas na base considerada para o relatório."
    )

    if concluidas:
        texto.append(
            f"- Destas, **{_fmt_int(concluidas)}** já se encontram concluídas, "
            f"o que corresponde a aproximadamente **{_fmt_percent(taxa_conclusao)}** do total."
        )
    else:
        texto.append(
            "- Não há registros marcados como concluídos dentro do recorte atual de filtros/período."
        )

    texto.append(
        f"- A taxa de solicitações marcadas como atrasadas está em torno de **{_fmt_percent(taxa_atraso)}**."
    )

    try:
        t = float(taxa_atraso)
    except Exception:
        t = None

    if t is not None:
        if t < 5:
            texto.append(
                "- **Leitura:** o nível de atraso é baixo, sugerindo boa aderência ao fluxo e prazos definidos."
            )
        elif t < 15:
            texto.append(
                "- **Leitura:** existe um nível moderado de atraso; vale monitorar os gargalos de forma contínua."
            )
        elif t < 30:
            texto.append(
                "- **Leitura:** o percentual de atraso já é relevante; recomenda-se priorizar ações de revisão de fluxo e reforço de capacidade."
            )
        else:
            texto.append(
                "- **Leitura:** o atraso é elevado, indicando possível sobrecarga de equipes, prazos subdimensionados ou falhas de governança do processo."
            )

    if nivel_detalhe.lower() == "detalhado":
        texto.append(
            "- Sugere-se acompanhar a evolução desses indicadores mês a mês, para diferenciar oscilações pontuais "
            "de tendências estruturais (crescimento contínuo de demanda ou queda de capacidade)."
        )

    texto.append("")
    return "\n".join(texto)


# ================== BLOCO 2 – FUNIL OPERACIONAL ==================

def _analisar_funil(funil_status: List[Dict[str, Any]], nivel_detalhe: str) -> str:
    texto = []
    texto.append("### 2. Análise do funil operacional (status macro)\n")

    if not funil_status:
        texto.append(
            "- Não foi possível calcular o funil, pois não há informações estruturadas de `status_macro` na base atual."
        )
        texto.append("")
        return "\n".join(texto)

    total = 0.0
    for linha in funil_status:
        try:
            total += float(linha.get("quantidade", 0))
        except Exception:
            continue

    if total == 0:
        texto.append(
            "- Existem registros de funil, mas a soma das quantidades é zero. "
            "Verifique se o filtro aplicado não esvaziou o conjunto de dados."
        )
        texto.append("")
        return "\n".join(texto)

    funil_ordenado = sorted(
        funil_status,
        key=lambda x: float(x.get("quantidade", 0) or 0),
        reverse=True,
    )

    if nivel_detalhe.lower() == "resumido":
        max_stages = 3
    elif nivel_detalhe.lower() == "detalhado":
        max_stages = min(8, len(funil_ordenado))
    else:
        max_stages = min(5, len(funil_ordenado))

    texto.append("- **Distribuição dos principais estágios do fluxo:**")
    for linha in funil_ordenado[:max_stages]:
        nome = str(linha.get("status_macro", "Sem rótulo"))
        qtd = linha.get("quantidade", 0)
        try:
            pct = float(qtd) / total * 100 if total else 0
        except Exception:
            pct = 0
        texto.append(
            f"  - `{nome}`: **{_fmt_int(qtd)}** solicitações (~{_fmt_percent(pct)})"
        )

    gargalo = funil_ordenado[0]
    nome_gargalo = str(gargalo.get("status_macro", "N/D"))
    qtd_gargalo = gargalo.get("quantidade", 0)
    pct_gargalo = float(qtd_gargalo) / total * 100 if total else 0

    texto.append(
        f"\n- **Possível gargalo:** o estágio com maior concentração é "
        f"`{nome_gargalo}`, reunindo aproximadamente **{_fmt_percent(pct_gargalo)}** "
        f"de todas as solicitações. Esse ponto deve ser priorizado em ações de melhoria."
    )

    if nivel_detalhe.lower() == "detalhado":
        texto.append(
            "- Em termos de gestão, vale mapear quais núcleos, órgãos ou responsáveis alimentam "
            "esse estágio com maior intensidade, para definir planos de ação mais direcionados."
        )

    texto.append("")
    return "\n".join(texto)


# ================== BLOCO 2B – PERFIL POR TIPO DE SOLICITAÇÃO ==================

def _analisar_tipos(distrib_tipo_solic: Optional[Dict[str, Any]],
                    nivel_detalhe: str) -> str:
    texto = []
    texto.append("### 3. Perfil dos tipos de solicitação\n")

    if not distrib_tipo_solic:
        texto.append(
            "- Não foi possível identificar a distribuição por tipo de solicitação. "
            "Verifique se a coluna de tipo está preenchida no conjunto de dados."
        )
        texto.append("")
        return "\n".join(texto)

    if nivel_detalhe.lower() == "resumido":
        top_n = 3
    elif nivel_detalhe.lower() == "detalhado":
        top_n = 8
    else:
        top_n = 5

    ordenado = _top_keys_ordenados(distrib_tipo_solic, top_n=top_n)
    total = sum(v for _, v in ordenado) or 0

    texto.append("- **Tipos de solicitação mais frequentes:**")
    for nome, qtd in ordenado:
        pct = qtd / total * 100 if total else 0
        texto.append(
            f"  - `{nome}` – **{_fmt_int(qtd)}** solicitações (~{_fmt_percent(pct)})"
        )

    if nivel_detalhe.lower() == "detalhado":
        texto.append(
            "- A concentração em poucos tipos de solicitação indica os principais \"produtos\" do processo. "
            "Vale avaliar se esses tipos possuem fluxos e checklists bem padronizados, para reduzir retrabalho e tempo de ciclo."
        )

    texto.append("")
    return "\n".join(texto)


# ================== BLOCO 2C – PERFIL POR SITUAÇÃO ATUAL ==================

def _analisar_situacao_atual(distrib_situacao_atual: Optional[Dict[str, Any]],
                             nivel_detalhe: str) -> str:
    texto = []
    texto.append("### 4. Distribuição da Situação Atual\n")

    if not distrib_situacao_atual:
        texto.append(
            "- Não foi possível identificar a distribuição da Situação Atual. "
            "Verifique se a coluna correspondente está preenchida no conjunto de dados."
        )
        texto.append("")
        return "\n".join(texto)

    if nivel_detalhe.lower() == "resumido":
        top_n = 3
    elif nivel_detalhe.lower() == "detalhado":
        top_n = 8
    else:
        top_n = 5

    ordenado = _top_keys_ordenados(distrib_situacao_atual, top_n=top_n)
    total = sum(v for _, v in ordenado) or 0

    texto.append("- **Principais Situações Atuais das solicitações:**")
    for nome, qtd in ordenado:
        pct = qtd / total * 100 if total else 0
        texto.append(
            f"  - `{nome}` – **{_fmt_int(qtd)}** solicitações (~{_fmt_percent(pct)})"
        )

    if nivel_detalhe.lower() == "detalhado":
        texto.append(
            "- Situações com grande volume (por exemplo, \"Em análise\", \"Aguardando informação\" ou equivalentes) "
            "podem esconder gargalos específicos, seja de tomada de decisão, de retorno de informação ou de disponibilidade de equipe."
        )

    texto.append("")
    return "\n".join(texto)


# ================== BLOCO 3 – RISCO ==================

def _analisar_risco(risco_por_categoria: Dict[str, Any], nivel_detalhe: str) -> str:
    texto = []
    texto.append("### 5. Mapa de risco das solicitações\n")

    if not risco_por_categoria:
        texto.append(
            "- Não foram encontradas informações agregadas de categoria de risco. "
            "É possível que a coluna `risco_categoria` não esteja preenchida para o recorte atual."
        )
        texto.append("")
        return "\n".join(texto)

    total = 0.0
    for v in risco_por_categoria.values():
        try:
            total += float(v)
        except Exception:
            continue

    if total == 0:
        texto.append(
            "- As categorias de risco existem, mas a contagem está zerada. "
            "Verifique se o filtro não removeu todos os casos."
        )
    else:
        if nivel_detalhe.lower() == "resumido":
            top_n = 3
        elif nivel_detalhe.lower() == "detalhado":
            top_n = 8
        else:
            top_n = 5

        ordenado = _top_keys_ordenados(risco_por_categoria, top_n=top_n)

        texto.append("- **Distribuição das categorias de risco mais frequentes:**")
        for cat, qtd in ordenado:
            pct = qtd / total * 100 if total else 0
            texto.append(
                f"  - **{cat}**: {_fmt_int(qtd)} solicitações (~{_fmt_percent(pct)})"
            )

        categorias_nomes = [c.lower() for c, _ in ordenado]

        if any("alto" in c for c in categorias_nomes):
            texto.append(
                "\n- Observa-se presença relevante de processos classificados como **Alto risco**, "
                "o que demanda acompanhamento prioritário, revisão de prazos e, se necessário, "
                "revisão da distribuição de carga entre núcleos e responsáveis."
            )
        if any("médio" in c or "medio" in c for c in categorias_nomes):
            texto.append(
                "- Há volume significativo em **risco médio**, o que pode evoluir para alto risco "
                "caso não haja monitoramento contínuo e atuação preventiva."
            )
        if any("baixo" in c for c in categorias_nomes):
            texto.append(
                "- A existência de uma base expressiva de casos em **baixo risco** indica que parte do fluxo está sob controle, "
                "servindo de referência para boas práticas a serem replicadas."
            )

    if nivel_detalhe.lower() == "detalhado":
        texto.append(
            "- Para cada categoria de risco, recomenda-se identificar padrões (tipo de solicitação, núcleo, órgão, "
            "responsável, etapa do fluxo) que mais contribuem para a recorrência e atuar de forma segmentada."
        )

    texto.append("")
    return "\n".join(texto)


# ================== BLOCO 4 – PROCESSOS CRÍTICOS ==================

def _resumir_processos_criticos(processos_criticos: List[Dict[str, Any]],
                                nivel_detalhe: str) -> str:
    texto = []
    texto.append("### 6. Principais processos críticos (amostra)\n")

    if not processos_criticos:
        texto.append(
            "- Não foram identificados processos críticos no recorte atual, ou a função de "
            "cálculo de risco ainda não foi aplicada de forma completa."
        )
        texto.append("")
        return "\n".join(texto)

    if nivel_detalhe.lower() == "resumido":
        max_itens = 3
    elif nivel_detalhe.lower() == "detalhado":
        max_itens = 10
    else:
        max_itens = 5

    texto.append(
        "- Abaixo uma amostra dos processos com maior `risco_score` dentro do recorte atual:"
    )

    for i, proc in enumerate(processos_criticos[:max_itens], start=1):
        numero = (
            proc.get("Número da Solicitação")
            or proc.get("Numero da Solicitação")
            or proc.get("numero")
        )
        responsavel = proc.get("Responsável") or proc.get("Responsavel") or "-"
        nucleo = (
            proc.get("Núcleo Pertencente")
            or proc.get("Núcleo")
            or proc.get("Nucleo")
            or "-"
        )
        risco_cat = proc.get("risco_categoria", "-")
        risco_score = proc.get("risco_score", "-")
        lead_time = proc.get("lead_time", "-")

        try:
            risco_score_fmt = f"{float(risco_score):.1f}"
        except Exception:
            risco_score_fmt = str(risco_score)

        try:
            lead_time_fmt = f"{float(lead_time):.1f} dias"
        except Exception:
            lead_time_fmt = str(lead_time)

        texto.append(
            f"  {i}. Solicitação **{numero}** – Responsável: **{responsavel}**, Núcleo: **{nucleo}**  \n"
            f"     • Categoria de risco: **{risco_cat}**  \n"
            f"     • Risco score: **{risco_score_fmt}**  \n"
            f"     • Lead time aproximado: **{lead_time_fmt}**"
        )

    texto.append(
        "\n- Recomenda-se acompanhar esses casos em reuniões de monitoramento, garantindo registro de plano de ação "
        "e prazos claros para a próxima etapa."
    )
    texto.append("")
    return "\n".join(texto)


# ================== BLOCO 5 – RECOMENDAÇÕES GERAIS ==================

def _gerar_recomendacoes(kpis: Dict[str, Any],
                         risco_por_categoria: Dict[str, Any],
                         funil_status: List[Dict[str, Any]],
                         nivel_detalhe: str) -> str:
    texto = []
    texto.append("### 7. Ações recomendadas e próximos passos\n")

    taxa_atraso = kpis.get("Taxa Atraso (%)", 0)
    try:
        t_atraso = float(taxa_atraso)
    except Exception:
        t_atraso = None

    if t_atraso is not None and t_atraso >= 15:
        texto.append(
            "- **Revisar prazos e capacidade instalada:** a taxa de atraso está acima de 15%, "
            "indicando necessidade de reavaliar a compatibilidade entre volume de demanda, "
            "capacidade das equipes e prazos definidos em SLA."
        )
    else:
        texto.append(
            "- **Manter monitoramento de prazos:** embora a taxa de atraso não seja crítica, "
            "é importante manter rotinas de acompanhamento e alertas precoces."
        )

    if funil_status:
        total = 0.0
        for linha in funil_status:
            try:
                total += float(linha.get("quantidade", 0))
            except Exception:
                continue

        if total > 0:
            funil_ordenado = sorted(
                funil_status,
                key=lambda x: float(x.get("quantidade", 0) or 0),
                reverse=True,
            )
            gargalo = funil_ordenado[0]
            nome_gargalo = str(gargalo.get("status_macro", "N/D"))
            qtd_gargalo = gargalo.get("quantidade", 0)
            pct_gargalo = float(qtd_gargalo) / total * 100 if total else 0

            texto.append(
                f"- **Tratar o principal gargalo do fluxo:** o estágio `{nome_gargalo}` concentra "
                f"cerca de **{_fmt_percent(pct_gargalo)}** das solicitações. Sugerem-se ações como:  \n"
                f"  • revisão de critérios de entrada e saída desse estágio;  \n"
                f"  • definição de prazos internos específicos;  \n"
                f"  • reforço de equipe ou automação de etapas repetitivas."
            )

    if risco_por_categoria:
        ordenado = _top_keys_ordenados(risco_por_categoria, top_n=3)
        if ordenado:
            texto.append(
                "- **Aprofundar análise de risco:** recomenda-se montar um painel periódico destacando, "
                "no mínimo, as três categorias de risco mais frequentes:"
            )
            for cat, qtd in ordenado:
                texto.append(
                    f"  • **{cat}** – {_fmt_int(qtd)} ocorrências no período analisado."
                )
            texto.append(
                "  Esses grupos devem ter planos de ação específicos, com responsáveis claros "
                "e prazos para redução de recorrência."
            )
    else:
        texto.append(
            "- **Estruturar classificação de risco:** como ainda não há categorização consolidada de risco, "
            "vale priorizar o preenchimento correto de campos-chave (status, prazos, datas de marcos) "
            "para permitir análises mais sofisticadas."
        )

    if nivel_detalhe.lower() == "detalhado":
        texto.append(
            "- Idealmente, o painel deve ser acoplado a uma rotina de governança (comitê, reunião de monitoramento), "
            "em que cada indicador possua um responsável, uma meta e um plano de ação associado."
        )

    texto.append(
        "\n- **Recomendação geral:** utilizar esta dashboard em rotinas quinzenais ou mensais, "
        "comparando a evolução dos indicadores ao longo do tempo e registrando decisões e responsáveis. "
        "Assim, o painel deixa de ser apenas um retrato estático e passa a ser uma ferramenta ativa de gestão."
    )

    texto.append("")
    return "\n".join(texto)


# ================== BLOCO 6 – FOCO EM ÓRGÃO & UG ==================

def _analise_orgao_ug(contexto_orgao: Optional[Dict[str, Any]],
                      nivel_detalhe: str) -> str:
    texto = []
    texto.append("### 8. Foco em Órgão & Unidade Gestora\n")

    if not contexto_orgao:
        texto.append(
            "- Não foi possível gerar uma análise específica por Órgão/UG, "
            "pois os campos necessários não foram identificados no recorte atual."
        )
        texto.append("")
        return "\n".join(texto)

    total_orgaos = contexto_orgao.get("total_orgaos", 0)
    total_ugs = contexto_orgao.get("total_ugs", 0)
    top_orgaos = contexto_orgao.get("top_orgaos", [])
    top_ugs = contexto_orgao.get("top_ugs", [])

    texto.append(
        f"- Foram identificados **{_fmt_int(total_orgaos)}** Órgãos distintos e **{_fmt_int(total_ugs)}** UGs "
        "no recorte utilizado para o relatório."
    )

    if top_orgaos:
        texto.append("- **Órgãos com maior volume de solicitações:**")
        limite = 3 if nivel_detalhe.lower() == "resumido" else 5
        for nome, qtd in top_orgaos[:limite]:
            texto.append(f"  - `{nome}` – **{_fmt_int(qtd)}** solicitações.")

    if top_ugs:
        texto.append("- **Unidades Gestoras mais demandadas:**")
        limite = 3 if nivel_detalhe.lower() == "resumido" else 5
        for nome, qtd in top_ugs[:limite]:
            texto.append(f"  - `{nome}` – **{_fmt_int(qtd)}** solicitações.")

    if nivel_detalhe.lower() == "detalhado":
        texto.append(
            "- Sugestão: para os Órgãos/UGs no topo do ranking, vale aprofundar quais tipos de solicitação "
            "e quais situações atuais mais contribuem para o volume e para o risco, distinguindo demanda "
            "estrutural de picos pontuais."
        )

    texto.append("")
    return "\n".join(texto)


# ================== BLOCO 7 – FOCO EM NÚCLEO & RESPONSÁVEL ==================

def _analise_nucleo_responsavel(contexto_nucleo: Optional[Dict[str, Any]],
                                nivel_detalhe: str) -> str:
    texto = []
    texto.append("### 8. Foco em Núcleo & Responsável\n")

    if not contexto_nucleo:
        texto.append(
            "- Não foi possível gerar uma análise específica por Núcleo/Responsável, "
            "pois os campos necessários não foram identificados no recorte atual."
        )
        texto.append("")
        return "\n".join(texto)

    total_nucleos = contexto_nucleo.get("total_nucleos", 0)
    total_resps = contexto_nucleo.get("total_responsaveis", 0)
    top_nucleos = contexto_nucleo.get("top_nucleos", [])
    top_resps = contexto_nucleo.get("top_responsaveis", [])

    texto.append(
        f"- Foram identificados **{_fmt_int(total_nucleos)}** Núcleos distintos e "
        f"**{_fmt_int(total_resps)}** Responsáveis distintos."
    )

    if top_nucleos:
        texto.append("- **Núcleos com maior volume de solicitações:**")
        limite = 3 if nivel_detalhe.lower() == "resumido" else 5
        for nome, qtd in top_nucleos[:limite]:
            texto.append(f"  - `{nome}` – **{_fmt_int(qtd)}** solicitações.")

    if top_resps:
        texto.append("- **Responsáveis mais demandados:**")
        limite = 3 if nivel_detalhe.lower() == "resumido" else 5
        for nome, qtd in top_resps[:limite]:
            texto.append(f"  - `{nome}` – **{_fmt_int(qtd)}** solicitações.")

    if nivel_detalhe.lower() == "detalhado":
        texto.append(
            "- Em termos de gestão de equipe, recomenda-se cruzar esse ranking com as categorias de risco "
            "e com o lead time médio, para identificar onde há sobrecarga, necessidade de apoio ou de revisão de processos."
        )

    texto.append("")
    return "\n".join(texto)


# ================== RELATÓRIO ANALÍTICO PADRÃO ==================

def gerar_relatorio_ia(
    kpis: Dict[str, Any],
    risco_por_categoria: Dict[str, Any],
    funil_status: List[Dict[str, Any]],
    processos_criticos: List[Dict[str, Any]],
    modo: str = "Executivo (geral)",
    contexto_orgao: Optional[Dict[str, Any]] = None,
    contexto_nucleo: Optional[Dict[str, Any]] = None,
    nivel_detalhe: str = "Padrão",
    periodo_label: str = "",
    distrib_tipo_solic: Optional[Dict[str, Any]] = None,
    distrib_situacao_atual: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Relatório analítico completo.
    """
    nivel_detalhe = nivel_detalhe or "Padrão"

    partes = []

    partes.append("# Relatório executivo automático\n")
    partes.append(
        f"_Modo de análise:_ **{modo}**  \n"
        f"_Nível de detalhe:_ **{nivel_detalhe}**"
    )
    if periodo_label:
        partes.append(f"_Período considerado:_ **{periodo_label}**")

    partes.append(
        "\n_Análise gerada automaticamente a partir dos dados filtrados na dashboard. "
        "Os comentários não substituem a avaliação técnica da equipe, mas servem como apoio à tomada de decisão._\n"
    )

    partes.append(_analisar_panorama(kpis, nivel_detalhe))
    partes.append(_analisar_funil(funil_status, nivel_detalhe))
    partes.append(_analisar_tipos(distrib_tipo_solic, nivel_detalhe))
    partes.append(_analisar_situacao_atual(distrib_situacao_atual, nivel_detalhe))
    partes.append(_analisar_risco(risco_por_categoria, nivel_detalhe))
    partes.append(_resumir_processos_criticos(processos_criticos, nivel_detalhe))
    partes.append(_gerar_recomendacoes(kpis, risco_por_categoria, funil_status, nivel_detalhe))

    modo_lower = modo.lower()
    if "órgão" in modo_lower or "orgão" in modo_lower or "orgao" in modo_lower:
        partes.append(_analise_orgao_ug(contexto_orgao, nivel_detalhe))
    elif "núcleo" in modo_lower or "nucleo" in modo_lower:
        partes.append(_analise_nucleo_responsavel(contexto_nucleo, nivel_detalhe))

    return "\n".join(partes)


# ================== CHECKLIST POR NÚCLEO ==================

def gerar_checklist_ia(
    kpis: Dict[str, Any],
    risco_por_categoria: Dict[str, Any],
    contexto_nucleo: Optional[Dict[str, Any]],
    periodo_label: str = "",
    nivel_detalhe: str = "Padrão",
) -> str:
    """
    Gera um checklist de ações por Núcleo, para ser usado em reunião de monitoramento.
    """
    partes = []
    partes.append("# Checklist de ação por Núcleo\n")

    if periodo_label:
        partes.append(f"_Período considerado:_ **{periodo_label}**\n")

    total = kpis.get("Total Solicitações", 0)
    taxa_atraso = kpis.get("Taxa Atraso (%)", 0)
    partes.append(
        f"- Volume de solicitações no período: **{_fmt_int(total)}**  \n"
        f"- Taxa de atraso estimada: **{_fmt_percent(taxa_atraso)}**\n"
    )

    if not contexto_nucleo or not contexto_nucleo.get("top_nucleos"):
        partes.append(
            "Não foi possível gerar checklist específico porque não há informações agregadas por Núcleo no recorte atual."
        )
        return "\n".join(partes)

    top_nucleos = contexto_nucleo.get("top_nucleos", [])
    if nivel_detalhe.lower() == "resumido":
        max_nuc = 3
    elif nivel_detalhe.lower() == "detalhado":
        max_nuc = min(10, len(top_nucleos))
    else:
        max_nuc = min(5, len(top_nucleos))

    partes.append(
        "_Sugestão: utilizar este checklist como pauta estruturada da reunião, passando núcleo a núcleo._\n"
    )

    for nome, qtd in top_nucleos[:max_nuc]:
        partes.append(f"## Núcleo: {nome}\n")
        partes.append(
            f"- Volume de solicitações atribuídas no período: **{_fmt_int(qtd)}**"
        )

        partes.append("**Checklist sugerido:**")
        partes.append(
            "- [ ] Revisar lista de solicitações em **alto risco** e definir prioridade de tratamento."
        )
        partes.append(
            "- [ ] Identificar processos parados em estágios intermediários (ex.: 'Em análise', 'Aguardando informação') e registrar causa principal."
        )
        partes.append(
            "- [ ] Conferir se todos os campos obrigatórios estão preenchidos (tipo, situação atual, responsável, prazos)."
        )
        partes.append(
            "- [ ] Validar se os prazos atuais são compatíveis com a capacidade da equipe e com a complexidade dos casos."
        )
        partes.append(
            "- [ ] Registrar, para cada gargalo identificado, um responsável e um prazo para a próxima ação."
        )
        if nivel_detalhe.lower() == "detalhado":
            partes.append(
                "- [ ] Mapear oportunidades de padronização (modelos de documentos, checklists internos, templates de resposta)."
            )
            partes.append(
                "- [ ] Avaliar necessidade de capacitação específica ou apoio de outros núcleos para casos recorrentes."
            )

        partes.append("")

    return "\n".join(partes)


# ================== MODELO DE ATA DE REUNIÃO ==================

def gerar_ata_reuniao_ia(
    kpis: Dict[str, Any],
    risco_por_categoria: Dict[str, Any],
    funil_status: List[Dict[str, Any]],
    contexto_orgao: Optional[Dict[str, Any]] = None,
    contexto_nucleo: Optional[Dict[str, Any]] = None,
    periodo_label: str = "",
    nivel_detalhe: str = "Padrão",
) -> str:
    """
    Gera um texto-modelo de ata de reunião de monitoramento, já preenchido com os principais indicadores.
    """
    total = kpis.get("Total Solicitações", 0)
    concluidas = kpis.get("Concluídas", 0)
    taxa_conclusao = kpis.get("Taxa Conclusão (%)", 0)
    taxa_atraso = kpis.get("Taxa Atraso (%)", 0)

    # identifica gargalo principal
    gargalo_nome = None
    if funil_status:
        funil_ordenado = sorted(
            funil_status,
            key=lambda x: float(x.get("quantidade", 0) or 0),
            reverse=True,
        )
        g = funil_ordenado[0]
        gargalo_nome = g.get("status_macro")

    # principais categorias de risco
    risco_top = _top_keys_ordenados(risco_por_categoria, top_n=3) if risco_por_categoria else []

    partes = []
    partes.append("# ATA DE REUNIÃO – Monitoramento de Solicitações\n")

    partes.append("**1. Dados da reunião**  ")
    partes.append("- Data: ____/____/______  ")
    partes.append("- Horário: ____:____  ")
    partes.append("- Local / Plataforma: _________________________  ")
    partes.append("- Coordenação: _______________________________  ")
    partes.append("- Participantes: _____________________________\n")

    partes.append("**2. Período analisado**  ")
    if periodo_label:
        partes.append(f"- Período de referência dos dados: **{periodo_label}**  ")
    else:
        partes.append("- Período de referência dos dados: ____________________  ")
    partes.append("")

    partes.append("**3. Principais indicadores apresentados**  ")
    partes.append(
        f"- Total de solicitações no período: **{_fmt_int(total)}**  "
    )
    partes.append(
        f"- Solicitações concluídas: **{_fmt_int(concluidas)}** "
        f"({ _fmt_percent(taxa_conclusao) } do total)  "
    )
    partes.append(
        f"- Taxa de atraso estimada: **{_fmt_percent(taxa_atraso)}**  "
    )
    if gargalo_nome:
        partes.append(
            f"- Estágio com maior acúmulo no funil: **`{gargalo_nome}`**  "
        )

    if risco_top:
        partes.append("- Categorias de risco mais frequentes:")
        for cat, qtd in risco_top:
            partes.append(f"  - {cat}: {_fmt_int(qtd)} ocorrências")
    partes.append("")

    if contexto_orgao:
        partes.append("**4. Destaques por Órgão / UG**  ")
        tot_o = contexto_orgao.get("total_orgaos", 0)
        tot_ug = contexto_orgao.get("total_ugs", 0)
        partes.append(
            f"- Órgãos analisados: **{_fmt_int(tot_o)}**  |  UGs analisadas: **{_fmt_int(tot_ug)}**"
        )
        top_orgaos = contexto_orgao.get("top_orgaos", [])[:3]
        if top_orgaos:
            partes.append("- Órgãos com maior volume de solicitações:")
            for nome, qtd in top_orgaos:
                partes.append(f"  - {nome}: {_fmt_int(qtd)} solicitações")
        partes.append("")

    if contexto_nucleo:
        partes.append("**5. Destaques por Núcleo / Responsável**  ")
        tn = contexto_nucleo.get("total_nucleos", 0)
        tr = contexto_nucleo.get("total_responsaveis", 0)
        partes.append(
            f"- Núcleos analisados: **{_fmt_int(tn)}**  |  Responsáveis: **{_fmt_int(tr)}**"
        )
        top_nucleos = contexto_nucleo.get("top_nucleos", [])[:3]
        if top_nucleos:
            partes.append("- Núcleos com maior volume de solicitações:")
            for nome, qtd in top_nucleos:
                partes.append(f"  - {nome}: {_fmt_int(qtd)} solicitações")
        partes.append("")

    partes.append("**6. Principais pontos discutidos**  ")
    partes.append("- __Ponto 1__: _____________________________  ")
    partes.append("- __Ponto 2__: _____________________________  ")
    partes.append("- __Ponto 3__: _____________________________  \n")

    partes.append("**7. Deliberações e planos de ação**  ")
    partes.append("- Ação 1: __________________________________________  ")
    partes.append("  - Responsável: __________________ Prazo: ___/___/_____  ")
    partes.append("- Ação 2: __________________________________________  ")
    partes.append("  - Responsável: __________________ Prazo: ___/___/_____  ")
    partes.append("- Ação 3: __________________________________________  ")
    partes.append("  - Responsável: __________________ Prazo: ___/___/_____  \n")

    partes.append("**8. Pendências e encaminhamentos**  ")
    partes.append("- Pendência 1: ______________________________________  ")
    partes.append("- Pendência 2: ______________________________________  \n")

    partes.append("**9. Encerramento**  ")
    partes.append(
        "Nada mais havendo a tratar, a reunião foi encerrada às ____:____, "
        "sendo lavrada a presente ata, que após lida e aprovada, vai assinada pelos presentes.\n"
    )

    partes.append("Assinaturas:  ")
    partes.append("- _______________________________________________  ")
    partes.append("- _______________________________________________  ")

    return "\n".join(partes)
