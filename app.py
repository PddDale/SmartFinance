import os
from datetime import datetime, date
import json
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, Response
import database
import models

app = Flask(__name__)
app.secret_key = "controle-financeiro-segredo-super-seguro"

# Inicializar banco de dados se necessário
database.init_db()

@app.template_filter("moeda")
def filter_moeda(valor):
    return models.formatar_moeda(valor)

@app.template_filter("data_br")
def filter_data_br(data_str):
    if not data_str:
        return ""
    try:
        parts = data_str.split("-")
        if len(parts) == 3:
            return f"{parts[2]}/{parts[1]}/{parts[0]}"
        elif len(parts) == 2:
            return f"{parts[1]}/{parts[0]}"
        return data_str
    except Exception:
        return data_str

@app.context_processor
def inject_global_data():
    """Injeta dados comuns em todas as páginas (KPIs de patrimônio, cartões, categorias)."""
    hoje = date.today()
    mes_atual = hoje.strftime("%Y-%m")
    ano_atual = hoje.year
    config = models.get_configuracoes()
    cartoes = models.get_cartoes()
    categorias = models.get_limites_categoria()

    # Total de faturas abertas em todos os cartões
    total_faturas_abertas = sum(c["fatura_aberta"] for c in cartoes)

    return {
        "global_config": config,
        "global_cartoes": cartoes,
        "global_categorias": categorias,
        "global_hoje": hoje.strftime("%Y-%m-%d"),
        "global_mes_atual": mes_atual,
        "global_ano_atual": ano_atual,
        "global_total_faturas_abertas": total_faturas_abertas
    }

# ----------------- ROTAS PRINCIPAIS -----------------

@app.route("/")
def index():
    """Dashboard principal com visão mensal, KPIs e gráficos."""
    hoje = date.today()
    ano_mes = request.args.get("mes", hoje.strftime("%Y-%m"))
    resumo = models.get_resumo_mensal(ano_mes)
    config = models.get_configuracoes()
    cartoes = models.get_cartoes()

    # Próximo e anterior mês para navegação
    try:
        dt = datetime.strptime(ano_mes + "-01", "%Y-%m-%d").date()
        mes_ant = models.add_months(dt, -1).strftime("%Y-%m")
        mes_prox = models.add_months(dt, 1).strftime("%Y-%m")
    except Exception:
        mes_ant = ano_mes
        mes_prox = ano_mes

    return render_template(
        "index.html",
        resumo=resumo,
        ano_mes=ano_mes,
        mes_ant=mes_ant,
        mes_prox=mes_prox,
        config=config,
        cartoes=cartoes
    )

@app.route("/lancamentos")
def lancamentos():
    """Página de gerenciamento de lançamentos avulsos diários com filtros."""
    hoje = date.today()
    filtro_mes = request.args.get("mes", "")
    filtro_cat = request.args.get("categoria", "")
    filtro_metodo = request.args.get("metodo", "")
    filtro_busca = request.args.get("busca", "").strip().lower()

    conn = database.get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT l.*, c.nome as cartao_nome, c.cor as cartao_cor,
               lim.cor as categoria_cor, lim.icone as categoria_icone
        FROM lancamentos l
        LEFT JOIN cartoes c ON l.cartao_id = c.id
        LEFT JOIN limites_categoria lim ON l.categoria = lim.categoria
        WHERE 1=1
    """
    params = []

    if filtro_mes:
        query += " AND (l.mes_vencimento = ? OR (l.cartao_id IS NULL AND l.ano_mes = ?))"
        params.extend([filtro_mes, filtro_mes])

    if filtro_cat:
        query += " AND l.categoria = ?"
        params.append(filtro_cat)

    if filtro_metodo:
        if filtro_metodo.startswith("cartao_"):
            cid = filtro_metodo.replace("cartao_", "")
            query += " AND l.cartao_id = ?"
            params.append(cid)
        else:
            query += " AND l.metodo_pagamento = ?"
            params.append(filtro_metodo)

    if filtro_busca:
        query += " AND (LOWER(l.descricao) LIKE ? OR LOWER(l.observacao) LIKE ?)"
        params.extend([f"%{filtro_busca}%", f"%{filtro_busca}%"])

    query += " ORDER BY l.data DESC, l.id DESC LIMIT 300;"
    cursor.execute(query, params)
    itens = [dict(r) for r in cursor.fetchall()]
    conn.close()

    total_filtrado = sum(float(i["valor"]) for i in itens)

    return render_template(
        "lancamentos.html",
        lancamentos=itens,
        total_filtrado=total_filtrado,
        filtro_mes=filtro_mes,
        filtro_cat=filtro_cat,
        filtro_metodo=filtro_metodo,
        filtro_busca=filtro_busca
    )

@app.route("/lancamentos/novo", methods=["POST"])
def novo_lancamento():
    """Adiciona um novo lançamento avulso."""
    try:
        data_compra = request.form.get("data")
        descricao = request.form.get("descricao", "").strip()
        categoria = request.form.get("categoria")
        valor = float(request.form.get("valor", 0).replace(",", "."))
        observacao = request.form.get("observacao", "").strip()
        metodo = request.form.get("metodo_pagamento")
        cartao_id = request.form.get("cartao_id")

        if not data_compra or not descricao or valor <= 0:
            flash("Preencha data, descrição e um valor positivo.", "danger")
            return redirect(request.referrer or url_for("lancamentos"))

        cid = int(cartao_id) if cartao_id and metodo == "Cartão de Crédito" else None

        models.add_lancamento(data_compra, descricao, categoria, valor, observacao, metodo, cid)
        flash(f"Lançamento '{descricao}' adicionado com sucesso!", "success")
    except Exception as e:
        flash(f"Erro ao salvar lançamento: {str(e)}", "danger")

    return redirect(request.referrer or url_for("lancamentos"))

@app.route("/lancamentos/editar/<int:id>", methods=["POST"])
def editar_lancamento(id):
    """Edita um lançamento avulso existente."""
    try:
        data_compra = request.form.get("data")
        descricao = request.form.get("descricao", "").strip()
        categoria = request.form.get("categoria")
        valor = float(request.form.get("valor", 0).replace(",", "."))
        observacao = request.form.get("observacao", "").strip()
        metodo = request.form.get("metodo_pagamento")
        cartao_id = request.form.get("cartao_id")

        cid = int(cartao_id) if cartao_id and metodo == "Cartão de Crédito" else None

        models.update_lancamento(id, data_compra, descricao, categoria, valor, observacao, metodo, cid)
        flash("Lançamento atualizado com sucesso!", "success")
    except Exception as e:
        flash(f"Erro ao atualizar: {str(e)}", "danger")

    return redirect(request.referrer or url_for("lancamentos"))

@app.route("/lancamentos/excluir/<int:id>", methods=["POST"])
def excluir_lancamento(id):
    """Exclui um lançamento avulso."""
    try:
        models.delete_lancamento(id)
        flash("Lançamento excluído com sucesso!", "info")
    except Exception as e:
        flash(f"Erro ao excluir: {str(e)}", "danger")

    return redirect(request.referrer or url_for("lancamentos"))

@app.route("/parcelas")
def parcelas():
    """Página de gerenciamento de compras parceladas e projeções futuras."""
    compras = models.get_compras_parceladas()
    hoje = date.today().strftime("%Y-%m")

    # Calcular totais
    total_em_parcelas = sum(c["valor_total"] - c["entrada"] for c in compras)
    total_ja_pago = sum(c["valor_pago"] for c in compras)
    saldo_devedor_total = total_em_parcelas - total_ja_pago

    return render_template(
        "parcelas.html",
        compras=compras,
        total_em_parcelas=total_em_parcelas,
        total_ja_pago=total_ja_pago,
        saldo_devedor_total=saldo_devedor_total,
        mes_atual=hoje
    )

@app.route("/parcelas/nova", methods=["POST"])
def nova_compra_parcelada():
    """Adiciona nova compra parcelada."""
    try:
        descricao = request.form.get("descricao", "").strip()
        data_compra = request.form.get("data_compra")
        valor_total = float(request.form.get("valor_total", 0).replace(",", "."))
        entrada = float(request.form.get("entrada", 0).replace(",", ".")) if request.form.get("entrada") else 0.0
        num_parcelas = int(request.form.get("num_parcelas", 1))
        categoria = request.form.get("categoria")
        metodo = request.form.get("metodo_pagamento")
        cartao_id = request.form.get("cartao_id")
        observacao = request.form.get("observacao", "").strip()

        cid = int(cartao_id) if cartao_id and metodo == "Cartão de Crédito" else None

        if not descricao or not data_compra or valor_total <= 0 or num_parcelas < 1:
            flash("Preencha descrição, data, valor e número de parcelas válido.", "danger")
            return redirect(url_for("parcelas"))

        models.add_compra_parcelada(descricao, data_compra, valor_total, entrada, num_parcelas, categoria, metodo, cid, observacao)
        flash(f"Compra parcelada '{descricao}' cadastrada com sucesso em {num_parcelas}x!", "success")
    except Exception as e:
        flash(f"Erro ao salvar compra parcelada: {str(e)}", "danger")

    return redirect(url_for("parcelas"))

@app.route("/parcelas/excluir/<int:id>", methods=["POST"])
def excluir_compra_parcelada(id):
    """Exclui compra parcelada e todas as suas projeções."""
    try:
        models.delete_compra_parcelada(id)
        flash("Compra parcelada e todas as suas parcelas foram excluídas!", "info")
    except Exception as e:
        flash(f"Erro ao excluir: {str(e)}", "danger")

    return redirect(url_for("parcelas"))

@app.route("/recorrentes")
def recorrentes():
    """Página de gerenciamento de gastos recorrentes (assinaturas e contas fixas)."""
    hoje = date.today()
    ano_mes = request.args.get("mes", hoje.strftime("%Y-%m"))

    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT r.*, ct.nome as cartao_nome, ct.cor as cartao_cor,
               COALESCE(s.ativo, r.ativo_padrao) as status_mes
        FROM gastos_recorrentes r
        LEFT JOIN recorrentes_status_mes s ON r.id = s.recorrente_id AND s.ano_mes = ?
        LEFT JOIN cartoes ct ON r.cartao_id = ct.id
        ORDER BY r.dia_cobranca ASC, r.descricao ASC;
    """, (ano_mes,))
    itens = [dict(r) for r in cursor.fetchall()]
    conn.close()

    total_mensal_ativo = sum(float(i["valor_mensal"]) for i in itens if i["status_mes"] == 1)

    return render_template(
        "recorrentes.html",
        recorrentes=itens,
        ano_mes=ano_mes,
        total_mensal_ativo=total_mensal_ativo
    )

@app.route("/recorrentes/novo", methods=["POST"])
def novo_recorrente():
    """Cadastra novo gasto recorrente."""
    try:
        descricao = request.form.get("descricao", "").strip()
        valor_mensal = float(request.form.get("valor_mensal", 0).replace(",", "."))
        categoria = request.form.get("categoria")
        dia_cobranca = int(request.form.get("dia_cobranca", 5))
        metodo = request.form.get("metodo_pagamento")
        cartao_id = request.form.get("cartao_id")

        cid = int(cartao_id) if cartao_id and metodo == "Cartão de Crédito" else None

        if not descricao or valor_mensal <= 0:
            flash("Preencha descrição e um valor positivo.", "danger")
            return redirect(url_for("recorrentes"))

        models.add_gasto_recorrente(descricao, valor_mensal, categoria, dia_cobranca, metodo, cid)
        flash(f"Gasto recorrente '{descricao}' adicionado com sucesso!", "success")
    except Exception as e:
        flash(f"Erro ao salvar: {str(e)}", "danger")

    return redirect(url_for("recorrentes"))

@app.route("/recorrentes/editar/<int:id>", methods=["POST"])
def editar_recorrente(id):
    """Atualiza gasto recorrente."""
    try:
        descricao = request.form.get("descricao", "").strip()
        valor_mensal = float(request.form.get("valor_mensal", 0).replace(",", "."))
        categoria = request.form.get("categoria")
        dia_cobranca = int(request.form.get("dia_cobranca", 5))
        metodo = request.form.get("metodo_pagamento")
        cartao_id = request.form.get("cartao_id")

        cid = int(cartao_id) if cartao_id and metodo == "Cartão de Crédito" else None

        models.update_gasto_recorrente(id, descricao, valor_mensal, categoria, dia_cobranca, metodo, cid)
        flash("Gasto recorrente atualizado com sucesso!", "success")
    except Exception as e:
        flash(f"Erro ao atualizar: {str(e)}", "danger")

    return redirect(url_for("recorrentes"))

@app.route("/recorrentes/excluir/<int:id>", methods=["POST"])
def excluir_recorrente(id):
    """Exclui gasto recorrente."""
    try:
        models.delete_gasto_recorrente(id)
        flash("Gasto recorrente removido!", "info")
    except Exception as e:
        flash(f"Erro ao excluir: {str(e)}", "danger")

    return redirect(url_for("recorrentes"))

@app.route("/api/recorrentes/toggle", methods=["POST"])
def toggle_recorrente():
    """Ativa ou pausa a cobrança de um gasto recorrente para determinado mês via AJAX."""
    try:
        data = request.get_json()
        recorrente_id = int(data.get("recorrente_id"))
        ano_mes = data.get("ano_mes")
        ativo = bool(data.get("ativo"))

        models.toggle_recorrente_mes(recorrente_id, ano_mes, ativo)
        return jsonify({"success": True, "ativo": ativo})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/cartoes")
def cartoes():
    """Página de múltiplos cartões de crédito com visualização de faturas e limites."""
    lista_cartoes = models.get_cartoes()
    hoje = date.today().strftime("%Y-%m")
    ano_mes = request.args.get("mes", hoje)

    # Detalhamento de cada cartão para o mês selecionado
    conn = database.get_db_connection()
    cursor = conn.cursor()

    for c in lista_cartoes:
        cid = c["id"]
        # Buscar compras avulsas desta fatura
        cursor.execute("""
            SELECT * FROM lancamentos
            WHERE cartao_id = ? AND mes_vencimento = ?
            ORDER BY data DESC;
        """, (cid, ano_mes))
        c["itens_avulsos"] = [dict(r) for r in cursor.fetchall()]

        # Buscar parcelas desta fatura
        cursor.execute("""
            SELECT p.*, cp.descricao as compra_descricao
            FROM parcelas_detalhe p
            JOIN compras_parceladas cp ON p.compra_id = cp.id
            WHERE cp.cartao_id = ? AND p.ano_mes = ?
            ORDER BY p.data_vencimento ASC;
        """, (cid, ano_mes))
        c["itens_parcelas"] = [dict(r) for r in cursor.fetchall()]

        # Buscar assinaturas ativas neste cartão
        cursor.execute("""
            SELECT r.*, COALESCE(s.ativo, r.ativo_padrao) as status_mes
            FROM gastos_recorrentes r
            LEFT JOIN recorrentes_status_mes s ON r.id = s.recorrente_id AND s.ano_mes = ?
            WHERE r.cartao_id = ?;
        """, (ano_mes, cid))
        c["itens_recorrentes"] = [dict(r) for r in cursor.fetchall() if r["status_mes"] == 1]

        c["total_fatura_mes"] = round(
            sum(float(x["valor"]) for x in c["itens_avulsos"]) +
            sum(float(x["valor"]) for x in c["itens_parcelas"]) +
            sum(float(x["valor_mensal"]) for x in c["itens_recorrentes"]),
            2
        )

    conn.close()

    total_limite_global = sum(c["limite_total"] for c in lista_cartoes)
    total_disponivel_global = sum(c["limite_disponivel"] for c in lista_cartoes)
    total_comprometido_global = sum(c["limite_comprometido"] for c in lista_cartoes)

    return render_template(
        "cartoes.html",
        cartoes=lista_cartoes,
        ano_mes=ano_mes,
        total_limite_global=total_limite_global,
        total_disponivel_global=total_disponivel_global,
        total_comprometido_global=total_comprometido_global
    )

@app.route("/cartoes/novo", methods=["POST"])
def novo_cartao():
    """Cadastra novo cartão de crédito."""
    try:
        nome = request.form.get("nome", "").strip()
        limite_total = float(request.form.get("limite_total", 0).replace(",", "."))
        fechamento_dia = int(request.form.get("fechamento_dia", 25))
        vencimento_dia = int(request.form.get("vencimento_dia", 5))
        cor = request.form.get("cor", "#3b82f6")
        bandeira = request.form.get("bandeira", "Mastercard")

        if not nome or limite_total <= 0:
            flash("Informe nome e limite total do cartão.", "danger")
            return redirect(url_for("cartoes"))

        models.add_cartao(nome, limite_total, fechamento_dia, vencimento_dia, cor, bandeira)
        flash(f"Cartão '{nome}' cadastrado com sucesso!", "success")
    except Exception as e:
        flash(f"Erro ao cadastrar cartão: {str(e)}", "danger")

    return redirect(url_for("cartoes"))

@app.route("/cartoes/editar/<int:id>", methods=["POST"])
def editar_cartao(id):
    """Edita dados do cartão de crédito."""
    try:
        nome = request.form.get("nome", "").strip()
        limite_total = float(request.form.get("limite_total", 0).replace(",", "."))
        fechamento_dia = int(request.form.get("fechamento_dia", 25))
        vencimento_dia = int(request.form.get("vencimento_dia", 5))
        cor = request.form.get("cor", "#3b82f6")
        bandeira = request.form.get("bandeira", "Mastercard")

        models.update_cartao(id, nome, limite_total, fechamento_dia, vencimento_dia, cor, bandeira)
        flash("Cartão atualizado com sucesso!", "success")
    except Exception as e:
        flash(f"Erro ao editar cartão: {str(e)}", "danger")

    return redirect(url_for("cartoes"))

@app.route("/cartoes/excluir/<int:id>", methods=["POST"])
def excluir_cartao(id):
    """Exclui cartão de crédito."""
    try:
        models.delete_cartao(id)
        flash("Cartão excluído com sucesso!", "info")
    except Exception as e:
        flash(f"Erro ao excluir cartão: {str(e)}", "danger")

    return redirect(url_for("cartoes"))

@app.route("/anual")
def anual():
    """Visão anual com comparativo dos 12 meses por categoria e gráficos."""
    hoje = date.today()
    ano = int(request.args.get("ano", hoje.year))
    dados_ano = models.get_visao_anual(ano)

    return render_template(
        "anual.html",
        dados=dados_ano,
        ano=ano
    )

@app.route("/configuracoes")
def configuracoes():
    """Página de configurações gerais, rendas, patrimônio e limites de categorias."""
    config = models.get_configuracoes()
    limites = models.get_limites_categoria()
    cartoes = models.get_cartoes()

    return render_template(
        "configuracoes.html",
        config=config,
        limites=limites,
        cartoes=cartoes
    )

@app.route("/configuracoes/salvar", methods=["POST"])
def salvar_configuracoes():
    """Salva rendas mensais e saldos de patrimônio."""
    try:
        salario = float(request.form.get("salario", 0).replace(",", "."))
        outras_rendas = float(request.form.get("outras_rendas", 0).replace(",", "."))
        saldo_cc = float(request.form.get("saldo_conta_corrente", 0).replace(",", "."))
        valor_investido = float(request.form.get("valor_investido", 0).replace(",", "."))

        models.update_configuracoes(salario, outras_rendas, saldo_cc, valor_investido)
        flash("Configurações e saldos atualizados com sucesso!", "success")
    except Exception as e:
        flash(f"Erro ao salvar configurações: {str(e)}", "danger")

    return redirect(url_for("configuracoes"))

@app.route("/configuracoes/saldos", methods=["POST"])
def salvar_saldos_rapido():
    """Ajuste rápido de saldos (utilizado no modal do cabeçalho)."""
    try:
        saldo_cc = float(request.form.get("saldo_conta_corrente", 0).replace(",", "."))
        valor_investido = float(request.form.get("valor_investido", 0).replace(",", "."))

        models.update_saldos(saldo_cc, valor_investido)
        flash("Saldos e patrimônio atualizados!", "success")
    except Exception as e:
        flash(f"Erro ao atualizar saldos: {str(e)}", "danger")

    return redirect(request.referrer or url_for("index"))

@app.route("/configuracoes/limites", methods=["POST"])
def salvar_limites_categoria():
    """Atualiza limites das categorias."""
    try:
        limites = models.get_limites_categoria()
        for l in limites:
            cat = l["categoria"]
            campo = f"limite_{cat}"
            if campo in request.form:
                novo_limite = float(request.form.get(campo, 0).replace(",", "."))
                models.update_limite_categoria(cat, novo_limite)

        flash("Limites por categoria atualizados com sucesso!", "success")
    except Exception as e:
        flash(f"Erro ao atualizar limites: {str(e)}", "danger")

    return redirect(url_for("configuracoes"))

@app.route("/configuracoes/carregar-demo", methods=["POST"])
def carregar_dados_demo():
    """Carrega dados demonstrativos completos e realistas."""
    try:
        database.popular_dados_exemplo()
        flash("Dados demonstrativos carregados com sucesso!", "success")
    except Exception as e:
        flash(f"Erro ao carregar dados: {str(e)}", "danger")

    return redirect(url_for("index"))

@app.route("/configuracoes/exportar-json")
def exportar_json():
    """Exporta todo o banco de dados no formato database.json."""
    dump = models.exportar_backup_json()
    json_bytes = json.dumps(dump, indent=2, ensure_ascii=False).encode("utf-8")
    return Response(
        json_bytes,
        mimetype="application/json",
        headers={"Content-Disposition": f"attachment;filename=database_financeiro_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"}
    )

@app.route("/api/calcular-fatura", methods=["POST"])
def api_calcular_fatura():
    """Retorna previsão em tempo real da fatura com base na data da compra e no cartão selecionado."""
    try:
        data = request.get_json()
        data_compra = data.get("data")
        cartao_id = int(data.get("cartao_id"))

        conn = database.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT fechamento_dia, vencimento_dia FROM cartoes WHERE id = ?", (cartao_id,))
        crow = cursor.fetchone()
        conn.close()

        if not crow:
            return jsonify({"success": False, "error": "Cartão não encontrado."}), 404

        fatura_mes, mes_venc, data_venc = database.calcular_fatura_e_vencimento(
            data_compra, crow["fechamento_dia"], crow["vencimento_dia"]
        )

        return jsonify({
            "success": True,
            "fatura_mes": fatura_mes,
            "mes_vencimento": mes_venc,
            "data_vencimento": data_venc,
            "fechamento_dia": crow["fechamento_dia"],
            "vencimento_dia": crow["vencimento_dia"]
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/categorizar", methods=["POST"])
def api_categorizar():
    """Classifica automaticamente uma despesa com base no texto da descrição."""
    try:
        dados = request.get_json(silent=True) or {}
        descricao = dados.get("descricao", "")
        resultado = models.classificar_despesa(descricao)
        return jsonify({
            "success": True,
            "descricao": descricao,
            "categoria": resultado.get("categoria"),
            "origem": resultado.get("origem"),
            "palavra_chave": resultado.get("palavra_chave", "")
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/encerrar", methods=["POST"])
def api_encerrar():
    """Encerra a aplicação permitindo escolher entre salvar as alterações ou sair sem salvar."""
    import threading
    import time

    try:
        dados = request.get_json(silent=True) or {}
        salvar = dados.get("salvar", True)

        if salvar:
            # Sincronizar e assegurar persistência no SQLite
            conn = database.get_db_connection()
            conn.commit()
            conn.close()
            msg = "Todas as alterações foram salvas com sucesso no banco de dados local. Encerrando o SmartFinance."
        else:
            msg = "SmartFinance encerrado sem salvar novas alterações pendentes."

        def finalizar_processo():
            time.sleep(0.6)
            os._exit(0)

        threading.Thread(target=finalizar_processo, daemon=True).start()

        return jsonify({
            "success": True,
            "salvou": salvar,
            "message": msg
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    try:
        import waitress
        print("=" * 64)
        print("   SmartFinance - Servidor WSGI de Alta Performance (Waitress)")
        print("   Acesso: http://127.0.0.1:5000")
        print("   Pressione CTRL+C ou utilize o botao 'Sair' na pagina para fechar.")
        print("=" * 64)
        waitress.serve(app, host="127.0.0.1", port=5000, threads=6)
    except ImportError:
        app.run(debug=False, host="127.0.0.1", port=5000)



