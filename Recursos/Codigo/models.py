import sqlite3
from datetime import datetime, date, timedelta
import calendar
import json
if __package__:
    from .database import CATEGORIAS_PADRAO, get_db_connection, calcular_fatura_e_vencimento, gerar_parcelas_compra, add_months
else:
    from database import CATEGORIAS_PADRAO, get_db_connection, calcular_fatura_e_vencimento, gerar_parcelas_compra, add_months

def formatar_moeda(valor):
    """Formata um float para padrão de moeda brasileira R$ 1.234,56."""
    if valor is None:
        valor = 0.0
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def get_configuracoes(ano=None):
    """Recupera preferências, saldos e renda mensal do ano selecionado."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM configuracoes WHERE id = 1;")
    row = cursor.fetchone()

    if not row:
        conn.close()
        return {
            "salario": 0.0,
            "outras_rendas": 0.0,
            "renda_total": 0.0,
            "saldo_conta_corrente": 0.0,
            "valor_investido": 0.0,
            "patrimonio_total": 0.0,
            "data_atualizacao": "",
            "salario_anual": 0.0,
            "outras_rendas_anuais": 0.0,
            "ano_ativo": date.today().year,
            "formato_data": "dd/mm/aaaa"
        }

    ano_ativo = int(ano or row["ano_ativo"] or date.today().year)
    cursor.execute("SELECT salario_mensal, outras_rendas_mensais FROM rendas_anuais WHERE ano = ?;", (ano_ativo,))
    renda_ano = cursor.fetchone()
    salario = float((renda_ano["salario_mensal"] if renda_ano else row["salario"]) or 0.0)
    outras_rendas = float((renda_ano["outras_rendas_mensais"] if renda_ano else row["outras_rendas"]) or 0.0)
    saldo_cc = float(row["saldo_conta_corrente"] or 0.0)
    invest = float(row["valor_investido"] or 0.0)
    conn.close()

    return {
        "salario": salario,
        "salario_anual": salario * 12,
        "outras_rendas": outras_rendas,
        "outras_rendas_anuais": outras_rendas * 12,
        "renda_total": salario + outras_rendas,
        "saldo_conta_corrente": saldo_cc,
        "valor_investido": invest,
        "patrimonio_total": saldo_cc + invest,
        "data_atualizacao": row["data_atualizacao"] or "",
        "ano_ativo": ano_ativo,
        "formato_data": row["formato_data"] or "dd/mm/aaaa"
    }

def update_configuracoes(salario, outras_rendas, saldo_conta_corrente, valor_investido, ano=None, formato_data=None):
    """Atualiza rendas do ano, saldos e preferências gerais."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT ano_ativo FROM configuracoes WHERE id = 1;")
    config = cursor.fetchone()
    ano = int(ano or (config["ano_ativo"] if config else date.today().year))
    cursor.execute("""
        INSERT INTO rendas_anuais (ano, salario_mensal, outras_rendas_mensais, data_atualizacao)
        VALUES (?, ?, ?, datetime('now', 'localtime'))
        ON CONFLICT(ano) DO UPDATE SET
            salario_mensal = excluded.salario_mensal,
            outras_rendas_mensais = excluded.outras_rendas_mensais,
            data_atualizacao = excluded.data_atualizacao;
    """, (ano, salario, outras_rendas))
    cursor.execute("""
        UPDATE configuracoes
        SET salario = ?, outras_rendas = ?, saldo_conta_corrente = ?, valor_investido = ?,
            ano_ativo = ?, formato_data = COALESCE(?, formato_data),
            data_atualizacao = datetime('now', 'localtime')
        WHERE id = 1;
    """, (salario, outras_rendas, saldo_conta_corrente, valor_investido, ano, formato_data))
    conn.commit()
    conn.close()

def update_ano_ativo(ano):
    """Persiste o ano selecionado e inicializa a renda deste ano, se necessário."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT salario, outras_rendas FROM configuracoes WHERE id = 1;")
    config = cursor.fetchone()
    if config is None:
        conn.close()
        raise ValueError("As configurações financeiras não foram inicializadas.")
    cursor.execute("""
        INSERT OR IGNORE INTO rendas_anuais (ano, salario_mensal, outras_rendas_mensais, data_atualizacao)
        VALUES (?, ?, ?, datetime('now', 'localtime'));
    """, (ano, config["salario"], config["outras_rendas"]))
    cursor.execute("UPDATE configuracoes SET ano_ativo = ? WHERE id = 1;", (ano,))
    conn.commit()
    conn.close()

def update_saldos(saldo_conta_corrente, valor_investido):
    """Atualização rápida do saldo da conta corrente e investimentos."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE configuracoes
        SET saldo_conta_corrente = ?, valor_investido = ?,
            data_atualizacao = datetime('now', 'localtime')
        WHERE id = 1;
    """, (saldo_conta_corrente, valor_investido))
    conn.commit()
    conn.close()

def get_limites_categoria():
    """Recupera a lista de categorias com seus respectivos limites mensais."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM limites_categoria ORDER BY categoria ASC;")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_limite_categoria(categoria, limite_mensal):
    """Atualiza o limite mensal de uma categoria."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE limites_categoria
        SET limite_mensal = ?
        WHERE categoria = ?;
    """, (limite_mensal, categoria))
    conn.commit()
    conn.close()

def get_cartoes():
    """Recupera todos os cartões cadastrados e calcula seus limites comprometidos."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM cartoes WHERE ativo = 1 ORDER BY nome ASC;")
    cartoes_rows = cursor.fetchall()

    hoje = date.today()
    dia_hoje = hoje.day
    mes_atual_str = hoje.strftime("%Y-%m")

    cartoes = []
    for crow in cartoes_rows:
        cid = crow["id"]
        limite_total = float(crow["limite_total"])
        fechamento_dia = crow["fechamento_dia"]
        vencimento_dia = crow["vencimento_dia"]

        # Calcular ciclo aberto atual do cartão
        if dia_hoje >= fechamento_dia:
            ciclo_aberto_date = add_months(date(hoje.year, hoje.month, 1), 1)
        else:
            ciclo_aberto_date = date(hoje.year, hoje.month, 1)
        ciclo_aberto_str = ciclo_aberto_date.strftime("%Y-%m")

        # Fatura aberta (lançamentos no ciclo de fechamento atual)
        cursor.execute("""
            SELECT COALESCE(SUM(valor), 0.0) FROM lancamentos
            WHERE cartao_id = ? AND fatura_mes = ?;
        """, (cid, ciclo_aberto_str))
        gasto_avulso_aberto = float(cursor.fetchone()[0])

        # Parcelas no ciclo aberto (aqui ano_mes de parcelas_detalhe é mes_vencimento)
        # Buscar mês de vencimento correspondente ao ciclo aberto
        _, mes_venc_aberto, dt_venc_aberto = calcular_fatura_e_vencimento(
            ciclo_aberto_date.strftime("%Y-%m") + f"-{min(fechamento_dia - 1, 28) if fechamento_dia > 1 else 1:02d}",
            fechamento_dia, vencimento_dia
        )

        cursor.execute("""
            SELECT COALESCE(SUM(p.valor), 0.0)
            FROM parcelas_detalhe p
            JOIN compras_parceladas c ON p.compra_id = c.id
            WHERE c.cartao_id = ? AND p.ano_mes = ?;
        """, (cid, mes_venc_aberto))
        gasto_parcelas_aberto = float(cursor.fetchone()[0])

        # Recorrentes ativos alocados neste cartão
        cursor.execute("""
            SELECT COALESCE(SUM(valor_mensal), 0.0)
            FROM gastos_recorrentes
            WHERE cartao_id = ? AND ativo_padrao = 1;
        """, (cid,))
        gasto_recorrente_mes = float(cursor.fetchone()[0])

        fatura_aberta_total = gasto_avulso_aberto + gasto_parcelas_aberto + gasto_recorrente_mes

        # Total comprometido no cartão (todas as parcelas pendentes daquele cartão + avulsos em aberto)
        cursor.execute("""
            SELECT COALESCE(SUM(p.valor), 0.0)
            FROM parcelas_detalhe p
            JOIN compras_parceladas c ON p.compra_id = c.id
            WHERE c.cartao_id = ? AND p.status = 'Pendente' AND p.ano_mes >= ?;
        """, (cid, mes_atual_str))
        total_parcelas_futuras = float(cursor.fetchone()[0])

        limite_comprometido = gasto_avulso_aberto + total_parcelas_futuras
        limite_disponivel = max(0.0, limite_total - limite_comprometido)
        pct_uso = (limite_comprometido / limite_total * 100) if limite_total > 0 else 0.0

        # Datas do próximo fechamento e próximo vencimento
        # Próximo fechamento:
        if dia_hoje < fechamento_dia:
            prox_fech_date = date(hoje.year, hoje.month, min(fechamento_dia, calendar.monthrange(hoje.year, hoje.month)[1]))
        else:
            prox_mes = add_months(hoje, 1)
            prox_fech_date = date(prox_mes.year, prox_mes.month, min(fechamento_dia, calendar.monthrange(prox_mes.year, prox_mes.month)[1]))

        # Próximo vencimento:
        if vencimento_dia > fechamento_dia:
            prox_venc_date = date(prox_fech_date.year, prox_fech_date.month, min(vencimento_dia, calendar.monthrange(prox_fech_date.year, prox_fech_date.month)[1]))
        else:
            vm = add_months(prox_fech_date, 1)
            prox_venc_date = date(vm.year, vm.month, min(vencimento_dia, calendar.monthrange(vm.year, vm.month)[1]))

        cartoes.append({
            "id": cid,
            "nome": crow["nome"],
            "limite_total": limite_total,
            "fechamento_dia": fechamento_dia,
            "vencimento_dia": vencimento_dia,
            "cor": crow["cor"] or "#3b82f6",
            "bandeira": crow["bandeira"] or "Mastercard",
            "fatura_aberta": fatura_aberta_total,
            "limite_comprometido": limite_comprometido,
            "limite_disponivel": limite_disponivel,
            "percentual_uso": round(pct_uso, 1),
            "proximo_fechamento": prox_fech_date.strftime("%d/%m/%Y"),
            "proximo_vencimento": prox_venc_date.strftime("%d/%m/%Y")
        })

    conn.close()
    return cartoes

def get_resumo_mensal(ano_mes):
    """
    Calcula todos os indicadores do mês selecionado:
    - Renda Total (Salário + Outras Rendas)
    - Total de Gastos (Avulsos com vencimento no mês + Parcelas no mês + Recorrentes ativos)
    - Saldo Líquido
    - % do Limite Utilizado
    - Progresso por Categoria
    - Faturas de Cartão no Mês
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    config = get_configuracoes(int(ano_mes[:4]))
    renda_total = config["renda_total"]

    # 1. Limites por categoria
    cursor.execute("SELECT categoria, limite_mensal, icone, cor FROM limites_categoria;")
    cat_rows = cursor.fetchall()
    categorias_map = {}
    limite_total_estipulado = 0.0
    for r in cat_rows:
        categorias_map[r["categoria"]] = {
            "categoria": r["categoria"],
            "limite": float(r["limite_mensal"]),
            "icone": r["icone"],
            "cor": r["cor"],
            "gasto_avulso": 0.0,
            "gasto_parcelas": 0.0,
            "gasto_recorrente": 0.0,
            "gasto_total": 0.0
        }
        limite_total_estipulado += float(r["limite_mensal"])

    # 2. Lançamentos avulsos
    # Lançamentos no cartão são alocados no mes_vencimento (ou fatura); lançamentos de outros métodos no ano_mes
    cursor.execute("""
        SELECT l.*, c.nome as cartao_nome, c.cor as cartao_cor
        FROM lancamentos l
        LEFT JOIN cartoes c ON l.cartao_id = c.id
        WHERE (l.cartao_id IS NOT NULL AND l.mes_vencimento = ?)
           OR (l.cartao_id IS NULL AND l.ano_mes = ?)
        ORDER BY l.data DESC;
    """, (ano_mes, ano_mes))
    lancamentos_mes = [dict(r) for r in cursor.fetchall()]

    total_avulsos = 0.0
    for l in lancamentos_mes:
        cat = l["categoria"]
        val = float(l["valor"])
        total_avulsos += val
        if cat in categorias_map:
            categorias_map[cat]["gasto_avulso"] += val
        else:
            if "Outros" in categorias_map:
                categorias_map["Outros"]["gasto_avulso"] += val

    # 3. Compras Parceladas (Parcelas do mês)
    cursor.execute("""
        SELECT p.*, c.descricao as compra_descricao, c.categoria, c.metodo_pagamento,
               ct.nome as cartao_nome, ct.cor as cartao_cor
        FROM parcelas_detalhe p
        JOIN compras_parceladas c ON p.compra_id = c.id
        LEFT JOIN cartoes ct ON c.cartao_id = ct.id
        WHERE p.ano_mes = ?
        ORDER BY p.data_vencimento ASC;
    """, (ano_mes,))
    parcelas_mes = [dict(r) for r in cursor.fetchall()]

    total_parcelas = 0.0
    for p in parcelas_mes:
        cat = p["categoria"]
        val = float(p["valor"])
        total_parcelas += val
        if cat in categorias_map:
            categorias_map[cat]["gasto_parcelas"] += val
        else:
            if "Outros" in categorias_map:
                categorias_map["Outros"]["gasto_parcelas"] += val

    # 4. Gastos Recorrentes do Mês
    cursor.execute("""
        SELECT r.*, ct.nome as cartao_nome, ct.cor as cartao_cor,
               COALESCE(s.ativo, r.ativo_padrao) as status_mes
        FROM gastos_recorrentes r
        LEFT JOIN recorrentes_status_mes s ON r.id = s.recorrente_id AND s.ano_mes = ?
        LEFT JOIN cartoes ct ON r.cartao_id = ct.id;
    """, (ano_mes,))
    recorrentes_todos = [dict(r) for r in cursor.fetchall()]

    recorrentes_ativos_mes = []
    total_recorrentes = 0.0
    for r in recorrentes_todos:
        if r["status_mes"] == 1:
            val = float(r["valor_mensal"])
            total_recorrentes += val
            cat = r["categoria"]
            if cat in categorias_map:
                categorias_map[cat]["gasto_recorrente"] += val
            else:
                if "Outros" in categorias_map:
                    categorias_map["Outros"]["gasto_recorrente"] += val
            recorrentes_ativos_mes.append(r)

    # 5. Consolidação de Gastos por Categoria
    categorias_lista = []
    for cat, dados in categorias_map.items():
        g_total = round(dados["gasto_avulso"] + dados["gasto_parcelas"] + dados["gasto_recorrente"], 2)
        dados["gasto_total"] = g_total
        lim = dados["limite"]
        dados["restante"] = round(lim - g_total, 2)
        pct = (g_total / lim * 100) if lim > 0 else (100.0 if g_total > 0 else 0.0)
        dados["percentual"] = round(pct, 1)

        if pct > 100:
            dados["status"] = "estourado"
            dados["badge_class"] = "bg-danger"
        elif pct >= 80:
            dados["status"] = "alerta"
            dados["badge_class"] = "bg-warning text-dark"
        else:
            dados["status"] = "normal"
            dados["badge_class"] = "bg-success"

        categorias_lista.append(dados)

    # Ordenar por maior gasto
    categorias_lista.sort(key=lambda x: x["gasto_total"], reverse=True)

    total_gastos = round(total_avulsos + total_parcelas + total_recorrentes, 2)
    saldo_liquido = round(renda_total - total_gastos, 2)
    pct_limite_global = round((total_gastos / limite_total_estipulado * 100), 1) if limite_total_estipulado > 0 else 0.0

    # 6. Faturas dos Cartões no mês selecionado
    cursor.execute("SELECT id, nome, cor FROM cartoes WHERE ativo = 1;")
    cartoes_db = cursor.fetchall()
    faturas_mes = []
    for c in cartoes_db:
        cid = c["id"]
        # Lançamentos avulsos deste cartão que vencem neste mês
        cursor.execute("SELECT COALESCE(SUM(valor), 0.0) FROM lancamentos WHERE cartao_id = ? AND mes_vencimento = ?;", (cid, ano_mes))
        v_avulsos = float(cursor.fetchone()[0])

        # Parcelas deste cartão que vencem neste mês
        cursor.execute("""
            SELECT COALESCE(SUM(p.valor), 0.0)
            FROM parcelas_detalhe p
            JOIN compras_parceladas cp ON p.compra_id = cp.id
            WHERE cp.cartao_id = ? AND p.ano_mes = ?;
        """, (cid, ano_mes))
        v_parc = float(cursor.fetchone()[0])

        # Recorrentes ativos neste cartão
        v_rec = 0.0
        for rec in recorrentes_ativos_mes:
            if rec["cartao_id"] == cid:
                v_rec += float(rec["valor_mensal"])

        tot_cartao = round(v_avulsos + v_parc + v_rec, 2)
        if tot_cartao > 0:
            faturas_mes.append({
                "cartao_id": cid,
                "cartao_nome": c["nome"],
                "cartao_cor": c["cor"] or "#3b82f6",
                "total": tot_cartao,
                "avulsos": v_avulsos,
                "parcelas": v_parc,
                "recorrentes": v_rec
            })

    # Dados para gráfico de pizza/donut de categorias (apenas categorias com gasto > 0)
    grafico_categorias = {
        "labels": [c["categoria"] for c in categorias_lista if c["gasto_total"] > 0],
        "valores": [c["gasto_total"] for c in categorias_lista if c["gasto_total"] > 0],
        "cores": [c["cor"] for c in categorias_lista if c["gasto_total"] > 0]
    }

    conn.close()

    # Formatação de mês para exibição amigável
    try:
        dt_obj = datetime.strptime(ano_mes, "%Y-%m")
        meses_pt = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
        nome_mes_extenso = f"{meses_pt[dt_obj.month - 1]} de {dt_obj.year}"
    except Exception:
        nome_mes_extenso = ano_mes

    return {
        "ano_mes": ano_mes,
        "nome_mes_extenso": nome_mes_extenso,
        "renda_total": renda_total,
        "limite_total_estipulado": limite_total_estipulado,
        "total_avulsos": total_avulsos,
        "total_parcelas": total_parcelas,
        "total_recorrentes": total_recorrentes,
        "total_gastos": total_gastos,
        "saldo_liquido": saldo_liquido,
        "percentual_limite": pct_limite_global,
        "categorias": categorias_lista,
        "faturas_cartoes": faturas_mes,
        "lancamentos_mes": lancamentos_mes,
        "parcelas_mes": parcelas_mes,
        "recorrentes_mes": recorrentes_ativos_mes,
        "grafico_categorias": grafico_categorias
    }

def get_visao_anual(ano):
    """
    Retorna a matriz comparativa e dados de gráfico para os 12 meses do ano especificado.
    """
    meses = [f"{ano}-{m:02d}" for m in range(1, 13)]
    meses_abrev = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

    config = get_configuracoes(ano)
    renda_mensal = config["renda_total"]

    limites = get_limites_categoria()
    categorias = [l["categoria"] for l in limites]
    categorias_cor = {l["categoria"]: l["cor"] for l in limites}

    # Inicializar estrutura de dados
    dados_categoria_mensal = {cat: [0.0] * 12 for cat in categorias}
    gastos_totais_mensais = [0.0] * 12
    renda_mensal_lista = [renda_mensal] * 12
    saldo_liquido_mensal = [0.0] * 12

    for idx, ano_mes in enumerate(meses):
        resumo = get_resumo_mensal(ano_mes)
        gastos_totais_mensais[idx] = resumo["total_gastos"]
        saldo_liquido_mensal[idx] = resumo["saldo_liquido"]

        for cat_info in resumo["categorias"]:
            cat = cat_info["categoria"]
            if cat in dados_categoria_mensal:
                dados_categoria_mensal[cat][idx] = cat_info["gasto_total"]

    # Calcular totais anuais por categoria e totais gerais
    tabela_anual = []
    total_geral_ano = sum(gastos_totais_mensais)
    for cat in categorias:
        valores_meses = dados_categoria_mensal[cat]
        tot_cat = sum(valores_meses)
        media_cat = round(tot_cat / 12, 2)
        pct_geral = round((tot_cat / total_geral_ano * 100), 1) if total_geral_ano > 0 else 0.0
        tabela_anual.append({
            "categoria": cat,
            "cor": categorias_cor.get(cat, "#6b7280"),
            "meses": valores_meses,
            "total_ano": round(tot_cat, 2),
            "media_mensal": media_cat,
            "percentual_total": pct_geral
        })

    # Ordenar tabela anual pelas categorias de maior gasto
    tabela_anual.sort(key=lambda x: x["total_ano"], reverse=True)

    # Gráfico de categorias empilhadas ou agrupadas
    datasets_categorias = []
    for cat in categorias:
        tot = sum(dados_categoria_mensal[cat])
        if tot > 0:
            datasets_categorias.append({
                "label": cat,
                "data": dados_categoria_mensal[cat],
                "backgroundColor": categorias_cor.get(cat, "#6b7280"),
            })

    return {
        "ano": ano,
        "meses_labels": meses_abrev,
        "tabela": tabela_anual,
        "gastos_totais_mensais": gastos_totais_mensais,
        "renda_mensal_lista": renda_mensal_lista,
        "saldo_liquido_mensal": saldo_liquido_mensal,
        "total_anual_gastos": round(total_geral_ano, 2),
        "total_anual_renda": round(renda_mensal * 12, 2),
        "saldo_anual": round((renda_mensal * 12) - total_geral_ano, 2),
        "media_mensal_gastos": round(total_geral_ano / 12, 2),
        "datasets_categorias": datasets_categorias
    }

# ----------------- OPERAÇÕES CRUD -----------------

def add_lancamento(data_compra, descricao, categoria, valor, observacao, metodo_pagamento, cartao_id=None):
    """Insere um novo gasto avulso calculando automaticamente o mês e a fatura."""
    conn = get_db_connection()
    cursor = conn.cursor()

    ano_mes = data_compra[:7]
    fatura_mes = None
    mes_vencimento = ano_mes
    data_vencimento = data_compra

    if cartao_id and metodo_pagamento == "Cartão de Crédito":
        cursor.execute("SELECT fechamento_dia, vencimento_dia FROM cartoes WHERE id = ?", (cartao_id,))
        crow = cursor.fetchone()
        if crow:
            fatura_mes, mes_vencimento, data_vencimento = calcular_fatura_e_vencimento(
                data_compra, crow["fechamento_dia"], crow["vencimento_dia"]
            )
    else:
        cartao_id = None

    cursor.execute("""
        INSERT INTO lancamentos (data, ano_mes, descricao, categoria, valor, observacao, metodo_pagamento, cartao_id, fatura_mes, mes_vencimento, data_vencimento)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (data_compra, ano_mes, descricao, categoria, valor, observacao, metodo_pagamento, cartao_id, fatura_mes, mes_vencimento, data_vencimento))

    conn.commit()
    conn.close()

def update_lancamento(lancamento_id, data_compra, descricao, categoria, valor, observacao, metodo_pagamento, cartao_id=None):
    """Atualiza um gasto avulso recalculando fatura e vencimentos."""
    conn = get_db_connection()
    cursor = conn.cursor()

    ano_mes = data_compra[:7]
    fatura_mes = None
    mes_vencimento = ano_mes
    data_vencimento = data_compra

    if cartao_id and metodo_pagamento == "Cartão de Crédito":
        cursor.execute("SELECT fechamento_dia, vencimento_dia FROM cartoes WHERE id = ?", (cartao_id,))
        crow = cursor.fetchone()
        if crow:
            fatura_mes, mes_vencimento, data_vencimento = calcular_fatura_e_vencimento(
                data_compra, crow["fechamento_dia"], crow["vencimento_dia"]
            )
    else:
        cartao_id = None

    cursor.execute("""
        UPDATE lancamentos
        SET data = ?, ano_mes = ?, descricao = ?, categoria = ?, valor = ?, observacao = ?,
            metodo_pagamento = ?, cartao_id = ?, fatura_mes = ?, mes_vencimento = ?, data_vencimento = ?
        WHERE id = ?;
    """, (data_compra, ano_mes, descricao, categoria, valor, observacao, metodo_pagamento, cartao_id, fatura_mes, mes_vencimento, data_vencimento, lancamento_id))

    conn.commit()
    conn.close()

def delete_lancamento(lancamento_id):
    """Remove um gasto avulso."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM lancamentos WHERE id = ?;", (lancamento_id,))
    conn.commit()
    conn.close()

def add_compra_parcelada(descricao, data_compra, valor_total, entrada, num_parcelas, categoria, metodo_pagamento, cartao_id, observacao=""):
    """Insere compra parcelada e projeta todas as parcelas."""
    conn = get_db_connection()
    cursor = conn.cursor()

    valor_financ = valor_total - entrada
    if num_parcelas <= 0:
        num_parcelas = 1
    valor_parcela = round(valor_financ / num_parcelas, 2)

    if cartao_id and metodo_pagamento == "Cartão de Crédito":
        cursor.execute("SELECT fechamento_dia, vencimento_dia FROM cartoes WHERE id = ?", (cartao_id,))
        crow = cursor.fetchone()
        _, mes_inicio, _ = calcular_fatura_e_vencimento(data_compra, crow["fechamento_dia"], crow["vencimento_dia"])
    else:
        cartao_id = None
        mes_inicio = data_compra[:7]

    dt_fim = add_months(datetime.strptime(mes_inicio + "-01", "%Y-%m-%d").date(), num_parcelas - 1)
    mes_fim = dt_fim.strftime("%Y-%m")

    cursor.execute("""
        INSERT INTO compras_parceladas (descricao, data_compra, valor_total, entrada, num_parcelas, valor_parcela, categoria, metodo_pagamento, cartao_id, mes_inicio, mes_fim, observacao)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (descricao, data_compra, valor_total, entrada, num_parcelas, valor_parcela, categoria, metodo_pagamento, cartao_id, mes_inicio, mes_fim, observacao))

    compra_id = cursor.lastrowid
    gerar_parcelas_compra(cursor, compra_id, data_compra, valor_total, entrada, num_parcelas, cartao_id)

    # Se houve entrada em dinheiro/conta corrente, opcionalmente registrar lançamento avulso no dia
    if entrada > 0:
        cursor.execute("""
            INSERT INTO lancamentos (data, ano_mes, descricao, categoria, valor, observacao, metodo_pagamento, mes_vencimento, data_vencimento)
            VALUES (?, ?, ?, ?, ?, ?, 'Cartão de Débito', ?, ?);
        """, (data_compra, data_compra[:7], f"Entrada: {descricao}", categoria, entrada, f"Entrada da compra parcelada #{compra_id}", data_compra[:7], data_compra))

    conn.commit()
    conn.close()

def delete_compra_parcelada(compra_id):
    """Remove uma compra parcelada e todas as suas parcelas."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM compras_parceladas WHERE id = ?;", (compra_id,))
    conn.commit()
    conn.close()

def excluir_dados_periodo(tipo, referencia):
    """Remove lançamentos e parcelas com datas dentro do período selecionado."""
    if tipo not in {"dia", "semana", "mes", "ano"}:
        raise ValueError("Selecione um período válido.")

    try:
        if tipo == "dia":
            inicio = date.fromisoformat(referencia)
            if inicio.isoformat() != referencia:
                raise ValueError
            fim = inicio
        elif tipo == "semana":
            inicio = date.fromisoformat(referencia)
            if inicio.isoformat() != referencia:
                raise ValueError
            inicio -= timedelta(days=inicio.weekday())
            fim = inicio + timedelta(days=6)
        elif tipo == "mes":
            inicio = date.fromisoformat(f"{referencia}-01")
            if inicio.strftime("%Y-%m") != referencia:
                raise ValueError
            fim = date(inicio.year, inicio.month, calendar.monthrange(inicio.year, inicio.month)[1])
        elif tipo == "ano":
            if len(referencia) != 4 or not referencia.isdigit():
                raise ValueError
            ano = int(referencia)
            if not 1 <= ano <= 9999:
                raise ValueError
            inicio = date(ano, 1, 1)
            fim = date(ano, 12, 31)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("Informe uma data válida para o período selecionado.") from None

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "DELETE FROM lancamentos WHERE data BETWEEN ? AND ?;",
            (inicio.isoformat(), fim.isoformat()),
        )
        lancamentos_excluidos = cursor.rowcount
        cursor.execute(
            "DELETE FROM parcelas_detalhe WHERE data_vencimento BETWEEN ? AND ?;",
            (inicio.isoformat(), fim.isoformat()),
        )
        parcelas_excluidas = cursor.rowcount
        cursor.execute("""
            DELETE FROM compras_parceladas
            WHERE NOT EXISTS (
                SELECT 1 FROM parcelas_detalhe
                WHERE parcelas_detalhe.compra_id = compras_parceladas.id
            );
        """)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {
        "lancamentos": lancamentos_excluidos,
        "parcelas": parcelas_excluidas,
        "inicio": inicio,
        "fim": fim,
    }

def excluir_todos_dados():
    """Apaga os dados financeiros e restaura configurações iniciais sem valores pessoais."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        for tabela in (
            "recorrentes_status_mes",
            "parcelas_detalhe",
            "lancamentos",
            "compras_parceladas",
            "gastos_recorrentes",
            "cartoes",
            "rendas_anuais",
            "configuracoes",
            "limites_categoria",
        ):
            cursor.execute(f"DELETE FROM {tabela};")

        ano_atual = date.today().year
        cursor.execute("""
            INSERT INTO configuracoes (
                id, salario, outras_rendas, saldo_conta_corrente, valor_investido,
                data_atualizacao, ano_ativo, formato_data
            ) VALUES (1, 0, 0, 0, 0, datetime('now', 'localtime'), ?, 'dd/mm/aaaa');
        """, (ano_atual,))
        cursor.execute("""
            INSERT INTO rendas_anuais (
                ano, salario_mensal, outras_rendas_mensais, data_atualizacao
            ) VALUES (?, 0, 0, datetime('now', 'localtime'));
        """, (ano_atual,))
        cursor.executemany("""
            INSERT INTO limites_categoria (categoria, limite_mensal, icone, cor)
            VALUES (?, 0, ?, ?);
        """, [(categoria, icone, cor) for categoria, _, icone, cor in CATEGORIAS_PADRAO])
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def get_compras_parceladas():
    """Retorna todas as compras parceladas com resumo de quitação."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT cp.*, ct.nome as cartao_nome, ct.cor as cartao_cor,
               (SELECT COUNT(*) FROM parcelas_detalhe pd WHERE pd.compra_id = cp.id AND pd.status = 'Pago') as parcelas_pagas,
               (SELECT COALESCE(SUM(pd.valor), 0.0) FROM parcelas_detalhe pd WHERE pd.compra_id = cp.id AND pd.status = 'Pago') as valor_pago
        FROM compras_parceladas cp
        LEFT JOIN cartoes ct ON cp.cartao_id = ct.id
        ORDER BY cp.data_compra DESC;
    """)
    compras = [dict(r) for r in cursor.fetchall()]

    for c in compras:
        compra_id = c["id"]
        cursor.execute("SELECT * FROM parcelas_detalhe WHERE compra_id = ? ORDER BY numero_parcela ASC;", (compra_id,))
        c["parcelas"] = [dict(p) for p in cursor.fetchall()]

    conn.close()
    return compras

def add_gasto_recorrente(descricao, valor_mensal, categoria, dia_cobranca, metodo_pagamento, cartao_id=None):
    """Cadastra novo gasto recorrente / assinatura."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if metodo_pagamento != "Cartão de Crédito":
        cartao_id = None
    cursor.execute("""
        INSERT INTO gastos_recorrentes (descricao, valor_mensal, categoria, dia_cobranca, metodo_pagamento, cartao_id, ativo_padrao)
        VALUES (?, ?, ?, ?, ?, ?, 1);
    """, (descricao, valor_mensal, categoria, dia_cobranca, metodo_pagamento, cartao_id))
    conn.commit()
    conn.close()

def update_gasto_recorrente(recorrente_id, descricao, valor_mensal, categoria, dia_cobranca, metodo_pagamento, cartao_id=None):
    """Atualiza dados de uma assinatura ou gasto recorrente."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if metodo_pagamento != "Cartão de Crédito":
        cartao_id = None
    cursor.execute("""
        UPDATE gastos_recorrentes
        SET descricao = ?, valor_mensal = ?, categoria = ?, dia_cobranca = ?, metodo_pagamento = ?, cartao_id = ?
        WHERE id = ?;
    """, (descricao, valor_mensal, categoria, dia_cobranca, metodo_pagamento, cartao_id, recorrente_id))
    conn.commit()
    conn.close()

def delete_gasto_recorrente(recorrente_id):
    """Remove um gasto recorrente."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM gastos_recorrentes WHERE id = ?;", (recorrente_id,))
    conn.commit()
    conn.close()

def toggle_recorrente_mes(recorrente_id, ano_mes, ativo):
    """Ativa ou pausa a cobrança de um gasto recorrente em um mês específico."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO recorrentes_status_mes (recorrente_id, ano_mes, ativo)
        VALUES (?, ?, ?)
        ON CONFLICT(recorrente_id, ano_mes) DO UPDATE SET ativo = excluded.ativo;
    """, (recorrente_id, ano_mes, 1 if ativo else 0))
    conn.commit()
    conn.close()

def add_cartao(nome, limite_total, fechamento_dia, vencimento_dia, cor="#3b82f6", bandeira="Mastercard"):
    """Cadastra novo cartão de crédito."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO cartoes (nome, limite_total, fechamento_dia, vencimento_dia, cor, bandeira, ativo)
        VALUES (?, ?, ?, ?, ?, ?, 1);
    """, (nome, limite_total, fechamento_dia, vencimento_dia, cor, bandeira))
    conn.commit()
    conn.close()

def update_cartao(cartao_id, nome, limite_total, fechamento_dia, vencimento_dia, cor, bandeira):
    """Atualiza dados do cartão e recalcula faturas pendentes."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE cartoes
        SET nome = ?, limite_total = ?, fechamento_dia = ?, vencimento_dia = ?, cor = ?, bandeira = ?
        WHERE id = ?;
    """, (nome, limite_total, fechamento_dia, vencimento_dia, cor, bandeira, cartao_id))

    # Recalcular datas dos lançamentos e parcelas ligados a este cartão
    cursor.execute("SELECT id, data FROM lancamentos WHERE cartao_id = ?;", (cartao_id,))
    for l in cursor.fetchall():
        fat_mes, mes_venc, dt_venc = calcular_fatura_e_vencimento(l["data"], fechamento_dia, vencimento_dia)
        cursor.execute("""
            UPDATE lancamentos
            SET fatura_mes = ?, mes_vencimento = ?, data_vencimento = ?
            WHERE id = ?;
        """, (fat_mes, mes_venc, dt_venc, l["id"]))

    conn.commit()
    conn.close()

def delete_cartao(cartao_id):
    """Remove um cartão de crédito."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cartoes WHERE id = ?;", (cartao_id,))
    conn.commit()
    conn.close()

def exportar_backup_json():
    """Gera um dump JSON completo estruturado conforme requisito da planilha."""
    conn = get_db_connection()
    cursor = conn.cursor()

    config = get_configuracoes()
    limites = get_limites_categoria()
    cartoes = [dict(r) for r in cursor.execute("SELECT * FROM cartoes;").fetchall()]
    lancamentos = [dict(r) for r in cursor.execute("SELECT * FROM lancamentos;").fetchall()]
    parceladas = [dict(r) for r in cursor.execute("SELECT * FROM compras_parceladas;").fetchall()]
    parcelas_detalhe = [dict(r) for r in cursor.execute("SELECT * FROM parcelas_detalhe;").fetchall()]
    recorrentes = [dict(r) for r in cursor.execute("SELECT * FROM gastos_recorrentes;").fetchall()]
    status_recorrentes = [dict(r) for r in cursor.execute("SELECT * FROM recorrentes_status_mes;").fetchall()]
    rendas_anuais = [
        dict(r) for r in cursor.execute("SELECT * FROM rendas_anuais ORDER BY ano;").fetchall()
    ]

    conn.close()

    limites_dict = {item["categoria"]: item["limite_mensal"] for item in limites}

    return {
        "configuracoes": {
            "salario": config["salario"],
            "outras_rendas": config["outras_rendas"],
            "limites_categoria": limites_dict,
            "ano_ativo": config["ano_ativo"],
            "formato_data": config["formato_data"],
            "rendas_anuais": rendas_anuais
        },
        "saldos": {
            "conta_corrente": config["saldo_conta_corrente"],
            "investimentos": config["valor_investido"],
            "patrimonio_total": config["patrimonio_total"]
        },
        "cartoes": cartoes,
        "lancamentos": lancamentos,
        "compras_parceladas": parceladas,
        "parcelas_detalhe": parcelas_detalhe,
        "gastos_recorrentes": recorrentes,
        "recorrentes_status_mes": status_recorrentes,
        "versao": "2.0",
        "data_exportacao": datetime.now().isoformat()
    }

# ----------------- MOTOR DE CLASSIFICAÇÃO AUTOMÁTICA DE DESPESAS -----------------

REGRAS_CATEGORIZACAO = {
    "Alimentação": [
        "ifood", "rappi", "mercado", "supermercado", "pão de açúcar", "carrefour", "extra", 
        "assai", "atacadão", "bar", "restaurante", "almoço", "jantar", "lanche", "padaria", 
        "açougue", "hortifruti", "mcdonald", "burger", "pizzaria", "café", "cafeteria", 
        "choperia", "churrascaria", "subway", "bobs", "comida", "refeição", "sorveteria"
    ],
    "Transporte": [
        "uber", "99", "99pop", "taxi", "combustível", "gasolina", "etanol", "posto", "ipiranga", 
        "shell", "br", "petrobras", "estacionamento", "sem parar", "pedagio", "pedágio", "veloe", 
        "bilhete", "metrô", "ônibus", "oficina", "mecânico", "pneu", "troca de óleo", "estapar"
    ],
    "Moradia": [
        "aluguel", "condomínio", "enel", "cpfl", "cemig", "luz", "energia", "sabesp", "sanepar", 
        "água", "gás", "internet", "claro", "vivo", "tim", "oi", "iptu", "reforma", "eletricista", 
        "encanador", "marcenaria", "limpeza", "diarista", "faxina", "copel", "comgás"
    ],
    "Saúde": [
        "farmácia", "drogaria", "droga raia", "drogasil", "pacheco", "são paulo", "remédio", 
        "medicamento", "consulta", "médico", "dentista", "odontologia", "psicólogo", "terapia", 
        "exame", "laboratório", "fleury", "unimed", "plano de saúde", "hospital", "ótica"
    ],
    "Lazer": [
        "netflix", "spotify", "amazon prime", "disney", "hbo", "max", "cinema", "ingresso", 
        "show", "teatro", "jogo", "steam", "playstation", "xbox", "nintendo", "balada", "festa", 
        "streaming", "parque", "clube", "passeio", "barzinho"
    ],
    "Educação": [
        "curso", "faculdade", "universidade", "mensalidade", "colégio", "escola", "livro", 
        "livraria", "udemy", "alura", "pós", "material escolar", "apostila", "idioma", "inglês", "cultura inglesa"
    ],
    "Vestuário": [
        "zara", "renner", "riachuelo", "c&a", "roupas", "camisa", "calça", "sapato", "calçados", 
        "tênis", "centauro", "nike", "adidas", "shein", "moda", "vestuário", "bolsa", "arezzo"
    ],
    "Tecnologia": [
        "kabum", "dell", "informática", "amazon", "apple", "celular", "smartphone", "notebook", 
        "computador", "fone", "teclado", "mouse", "processador", "hardware", "eletrônicos", "pichau", "terabyte"
    ],
    "Pessoal": [
        "perfume", "salão", "cabelo", "estética", "manicure", "depilação", "barbearia", 
        "cosméticos", "maquiagem", "boticário", "natura", "sephora"
    ],
    "Viagens": [
        "decolar", "latam", "gol", "azul", "booking", "airbnb", "hotel", "pousada", 
        "passagem", "aeroporto", "milhas", "trip", "cvc", "hostel"
    ]
}

def classificar_despesa(descricao):
    """
    Classifica automaticamente uma despesa com base em:
    1. Memória do histórico do usuário no banco SQLite.
    2. Dicionário contextual de padrões e palavras-chave.
    """
    if not descricao:
        return {"categoria": None, "origem": "nenhuma"}

    desc_lower = descricao.strip().lower()

    # 1. Checar memória do usuário no banco SQLite
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT categoria, COUNT(*) as qtd
            FROM lancamentos
            WHERE LOWER(descricao) = ?
            GROUP BY categoria
            ORDER BY qtd DESC
            LIMIT 1;
        """, (desc_lower,))
        row = cursor.fetchone()
        if row:
            conn.close()
            return {"categoria": row["categoria"], "origem": "historico_usuario"}

        # Busca aproximada por palavras-chave com mais de 3 caracteres
        palavras = [p for p in desc_lower.split() if len(p) >= 4]
        for p in palavras:
            cursor.execute("""
                SELECT categoria, COUNT(*) as qtd
                FROM lancamentos
                WHERE LOWER(descricao) LIKE ?
                GROUP BY categoria
                ORDER BY qtd DESC
                LIMIT 1;
            """, (f"%{p}%",))
            row = cursor.fetchone()
            if row:
                conn.close()
                return {"categoria": row["categoria"], "origem": "historico_aproximado"}
        conn.close()
    except Exception:
        pass

    # 2. Checar dicionário contextual
    for cat, palavras_chave in REGRAS_CATEGORIZACAO.items():
        for palavra in palavras_chave:
            if palavra in desc_lower:
                return {"categoria": cat, "origem": "regras_inteligentes", "palavra_chave": palavra}

    return {"categoria": "Outros", "origem": "padrao"}
