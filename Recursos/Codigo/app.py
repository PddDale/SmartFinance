import os
from datetime import datetime, date
import json
import io
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response
from jinja2 import pass_context
from werkzeug.exceptions import RequestEntityTooLarge

if __package__:
    from . import database, models
else:
    import database
    import models

PROJECT_DIR = Path(__file__).resolve().parents[2]
RESOURCE_DIR = PROJECT_DIR / "Recursos"
app = Flask(
    __name__,
    template_folder=str(RESOURCE_DIR / "Interface" / "templates"),
    static_folder=str(RESOURCE_DIR / "Interface" / "static")
)
app.secret_key = "controle-financeiro-segredo-super-seguro"
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

@app.errorhandler(RequestEntityTooLarge)
def arquivo_muito_grande(_erro):
    if request.path.startswith("/lancamentos/importar"):
        return jsonify({
            "success": False,
            "error": "O arquivo excede o limite de 10 MB.",
        }), 413
    return "A requisição excede o limite de tamanho permitido.", 413

# Inicializar banco de dados se necessário
database.init_db()

@app.template_filter("moeda")
def filter_moeda(valor):
    return models.formatar_moeda(valor)

@app.template_filter("decimal_br")
def filter_decimal_br(valor):
    if valor is None:
        valor = 0
    return f"{float(valor):.2f}".replace(".", ",")

@app.template_filter("data_br")
@pass_context
def filter_data_br(context, data_str):
    if not data_str:
        return ""
    formato = context.get("global_config", {}).get("formato_data", "dd/mm/aaaa")
    meses = [
        "janeiro", "fevereiro", "março", "abril", "maio", "junho",
        "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"
    ]
    dias_semana = [
        "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
        "sexta-feira", "sábado", "domingo"
    ]
    try:
        partes = data_str.split("-")
        if len(partes) == 3:
            data = date.fromisoformat(data_str)
            if formato == "extenso":
                return f"{data.day} de {meses[data.month - 1]} de {data.year}"
            if formato == "semana_extenso":
                return f"{dias_semana[data.weekday()]}, {data.day} de {meses[data.month - 1]} de {data.year}"
            return data.strftime("%d/%m/%Y")
        if len(partes) == 2:
            ano, mes = (int(parte) for parte in partes)
            if formato == "dd/mm/aaaa":
                return f"{mes:02d}/{ano:04d}"
            return f"{meses[mes - 1]} de {ano}"
    except (ValueError, TypeError, IndexError):
        return data_str
    return data_str

def parse_valor_localizado(valor):
    """Converte valores em formato brasileiro ou internacional para float."""
    texto = str(valor or "0").strip().replace("R$", "").replace(" ", "")
    if not texto:
        return 0.0
    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"-?\d{1,3}(?:\.\d{3})+", texto):
        texto = texto.replace(".", "")
    try:
        resultado = Decimal(texto)
    except InvalidOperation:
        raise ValueError(f"Valor monetário inválido: {valor}") from None
    if not resultado.is_finite():
        raise ValueError("Informe um valor monetário finito.")
    return float(resultado)

def parse_valor_importacao(valor, formato_decimal):
    """Converte um valor da planilha usando o formato decimal selecionado."""
    if formato_decimal == "auto":
        return parse_valor_localizado(valor)
    if formato_decimal not in {"brasileiro", "internacional"}:
        raise ValueError("Selecione um padrão decimal válido.")

    if isinstance(valor, (int, float, Decimal)) and not isinstance(valor, bool):
        resultado = Decimal(str(valor))
    else:
        texto = str(valor or "").strip().replace("R$", "").replace(" ", "")
        if not texto:
            raise ValueError("Valor monetário vazio.")
        if formato_decimal == "brasileiro":
            padrao = r"-?(?:\d+|\d{1,3}(?:\.\d{3})+)(?:,\d+)?"
            texto_normalizado = texto.replace(".", "").replace(",", ".")
        else:
            padrao = r"-?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?"
            texto_normalizado = texto.replace(",", "")
        if not re.fullmatch(padrao, texto):
            nome_formato = (
                "brasileiro (1.234,56)"
                if formato_decimal == "brasileiro"
                else "internacional (1,234.56)"
            )
            raise ValueError(f"Valor inválido para o padrão {nome_formato}: {valor}")
        resultado = Decimal(texto_normalizado)

    if not resultado.is_finite():
        raise ValueError("Informe um valor monetário finito.")
    return float(resultado)

def _normalizar_categoria_importada(valor):
    return "".join(
        caractere.casefold() for caractere in str(valor or "")
        if caractere.isalnum()
    )

def _ler_planilha_excel(arquivo):
    from openpyxl import load_workbook

    workbook = load_workbook(io.BytesIO(arquivo), read_only=True, data_only=True)
    planilha = workbook.active
    if planilha is None:
        workbook.close()
        raise ValueError("O arquivo não contém uma aba de planilha.")
    linhas = planilha.iter_rows(values_only=True)
    cabecalhos = next(linhas, None)
    if not cabecalhos:
        workbook.close()
        raise ValueError("A planilha está vazia ou não possui cabeçalho.")
    colunas = [
        {"indice": indice, "nome": str(nome).strip() if nome is not None else ""}
        for indice, nome in enumerate(cabecalhos)
    ]
    registros = [tuple(linha) for linha in linhas]
    workbook.close()
    return colunas, registros

def _data_excel_para_iso(valor):
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    texto = str(valor or "").strip()
    if not texto:
        raise ValueError("data vazia")
    try:
        return date.fromisoformat(texto).isoformat()
    except ValueError:
        for formato in ("%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(texto, formato).date().isoformat()
            except ValueError:
                continue
    raise ValueError("data inválida (use dd/mm/aaaa)")

@app.context_processor
def inject_global_data():
    """Injeta dados comuns em todas as páginas (KPIs de patrimônio, cartões, categorias)."""
    hoje = date.today()
    mes_atual = hoje.strftime("%Y-%m")
    ano_atual = hoje.year
    config = models.get_configuracoes(ano_atual, mes_atual)
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
    agora = datetime.now()
    hoje = agora.date()
    preferencias = models.get_configuracoes()
    mes_padrao = (
        hoje.strftime("%Y-%m")
        if preferencias["ano_ativo"] == hoje.year
        else f"{preferencias['ano_ativo']}-01"
    )
    ano_mes = request.args.get("mes", mes_padrao)
    try:
        ano_mes = datetime.strptime(ano_mes, "%Y-%m").strftime("%Y-%m")
    except ValueError:
        ano_mes = mes_padrao
    resumo = models.get_resumo_mensal(ano_mes)
    config = models.get_configuracoes(int(ano_mes[:4]), ano_mes)
    cartoes = models.get_cartoes()
    saudacao = (
        "Bom dia" if 5 <= agora.hour < 12
        else "Boa tarde" if 12 <= agora.hour < 18
        else "Boa noite"
    )

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
        cartoes=cartoes,
        data_atual=hoje.isoformat(),
        saudacao=saudacao
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

    query += " ORDER BY date(l.data) DESC, l.id DESC LIMIT 300;"
    cursor.execute(query, params)
    itens = [dict(r) for r in cursor.fetchall()]
    conn.close()

    total_filtrado = sum(float(i["valor"]) for i in itens)
    pagamentos_pendentes = models.get_pagamentos_recorrentes_pendentes(hoje)
    grupos_pagamentos_recorrentes = {}
    for pagamento in pagamentos_pendentes:
        grupos_pagamentos_recorrentes.setdefault(
            pagamento["id"], []
        ).append(pagamento)

    return render_template(
        "lancamentos.html",
        lancamentos=itens,
        grupos_pagamentos_recorrentes=list(grupos_pagamentos_recorrentes.values()),
        total_filtrado=total_filtrado,
        filtro_mes=filtro_mes,
        ano_filtro_mes=filtro_mes[:4] if filtro_mes else str(hoje.year),
        filtro_cat=filtro_cat,
        filtro_metodo=filtro_metodo,
        filtro_busca=filtro_busca
    )

@app.route("/api/lancamentos/sugestoes")
def sugestoes_lancamentos():
    """Sugere descrições já usadas em lançamentos anteriores."""
    termo = request.args.get("q", "").strip()
    if not termo:
        return jsonify({"sugestoes": []})

    termo_escapado = (
        termo.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT descricao
        FROM lancamentos
        WHERE descricao LIKE ? ESCAPE '\\'
        ORDER BY data DESC, id DESC
        LIMIT 100;
    """, (f"{termo_escapado}%",))
    sugestoes = list(dict.fromkeys(row["descricao"] for row in cursor.fetchall()))[:8]
    conn.close()
    return jsonify({"sugestoes": sugestoes})

@app.route("/lancamentos/importar/previa", methods=["POST"])
def previa_importacao_excel():
    """Lê o cabeçalho e algumas linhas para a etapa de mapeamento do wizard."""
    arquivo = request.files.get("arquivo")
    if not arquivo or not arquivo.filename or not arquivo.filename.lower().endswith(".xlsx"):
        return jsonify({"success": False, "error": "Selecione um arquivo Excel .xlsx."}), 400
    try:
        colunas, linhas = _ler_planilha_excel(arquivo.read())
        amostras = [
            [str(valor) if valor is not None else "" for valor in linha]
            for linha in linhas if any(valor is not None for valor in linha)
        ][:5]
        if not any(coluna["nome"] for coluna in colunas):
            raise ValueError("A primeira linha da planilha precisa conter os nomes das colunas.")
        return jsonify({
            "success": True,
            "colunas": colunas,
            "amostras": amostras,
            "total_linhas": sum(1 for linha in linhas if any(v is not None for v in linha)),
        })
    except ValueError as erro:
        return jsonify({"success": False, "error": str(erro)}), 400
    except Exception:
        app.logger.exception("Erro ao ler planilha Excel enviada para prévia")
        return jsonify({"success": False, "error": "Não foi possível ler esse arquivo Excel."}), 400

@app.route("/lancamentos/importar", methods=["POST"])
def importar_excel():
    """Valida todas as linhas mapeadas antes de gravar lançamentos em lote."""
    arquivo = request.files.get("arquivo")
    if not arquivo or not arquivo.filename or not arquivo.filename.lower().endswith(".xlsx"):
        return jsonify({"success": False, "error": "Selecione um arquivo Excel .xlsx."}), 400
    try:
        colunas, linhas = _ler_planilha_excel(arquivo.read())
        if len(linhas) > 20000:
            raise ValueError("A planilha excede o limite de 20.000 linhas de dados.")
        indices = {
            campo: int(request.form.get(f"{campo}_col", "-1"))
            for campo in ("data", "descricao", "valor")
        }
        categoria_col_texto = request.form.get("categoria_col", "")
        categoria_col = (
            int(categoria_col_texto) if categoria_col_texto.strip() else None
        )
        if len(set(indices.values())) != 3 or any(
            indice < 0 or indice >= len(colunas) for indice in indices.values()
        ):
            raise ValueError("Selecione uma coluna diferente para data, nome da compra e preço.")
        if categoria_col is not None and (
            categoria_col < 0
            or categoria_col >= len(colunas)
            or categoria_col in indices.values()
        ):
            raise ValueError("Selecione uma coluna de categoria válida e diferente das demais.")

        formato_decimal = request.form.get("formato_decimal", "auto")
        if formato_decimal not in {"auto", "brasileiro", "internacional"}:
            raise ValueError("Selecione um padrão decimal válido.")
        categoria = request.form.get("categoria", "Outros")
        metodo = request.form.get("metodo_pagamento", "Pix")
        categorias_validas = {item["categoria"] for item in models.get_limites_categoria()}
        categorias_por_nome = {
            _normalizar_categoria_importada(item): item
            for item in categorias_validas
        }
        if categoria_col is None and categoria not in categorias_validas:
            raise ValueError("Selecione uma categoria válida.")
        if metodo not in {"Cartão de Débito", "Pix", "Dinheiro", "Cartão de Crédito"}:
            raise ValueError("Selecione um método de pagamento válido.")
        cartao_id_texto = request.form.get("cartao_id", "")
        cartao_id = (
            int(cartao_id_texto)
            if metodo == "Cartão de Crédito" and cartao_id_texto
            else None
        )
        if metodo == "Cartão de Crédito" and not cartao_id:
            raise ValueError("Selecione o cartão de crédito utilizado.")

        registros = []
        erros = []
        for numero_linha, linha in enumerate(linhas, start=2):
            if not any(valor is not None and str(valor).strip() for valor in linha):
                continue
            try:
                descricao = str(linha[indices["descricao"]] or "").strip()
                data_compra = _data_excel_para_iso(linha[indices["data"]])
                valor = parse_valor_importacao(
                    linha[indices["valor"]], formato_decimal
                )
                categoria_linha = categoria
                if categoria_col is not None:
                    categoria_planilha = str(linha[categoria_col] or "").strip()
                    categoria_linha = categorias_por_nome.get(
                        _normalizar_categoria_importada(categoria_planilha)
                    )
                    if not categoria_linha:
                        raise ValueError(
                            f"categoria inválida ou vazia: '{categoria_planilha}'"
                        )
                if not descricao:
                    raise ValueError("nome da compra vazio")
                if valor <= 0:
                    raise ValueError("o preço precisa ser maior que zero")
                registros.append({
                    "data": data_compra,
                    "descricao": descricao,
                    "categoria": categoria_linha,
                    "valor": valor,
                    "metodo_pagamento": metodo,
                    "cartao_id": cartao_id,
                    "observacao": "Importado de planilha Excel",
                })
            except (IndexError, TypeError, ValueError) as erro:
                erros.append(f"Linha {numero_linha}: {erro}")
                if len(erros) == 10:
                    break
        if erros:
            return jsonify({
                "success": False,
                "error": "A planilha tem dados que precisam ser corrigidos; nenhum lançamento foi importado.",
                "erros": erros,
            }), 400
        if not registros:
            raise ValueError("Não há linhas preenchidas para importar.")
        models.importar_lancamentos(registros)
        return jsonify({
            "success": True,
            "quantidade": len(registros),
            "message": f"{len(registros)} lançamento(s) importado(s) com sucesso.",
        })
    except ValueError as erro:
        return jsonify({"success": False, "error": str(erro)}), 400
    except Exception:
        app.logger.exception("Erro ao importar lançamentos da planilha Excel")
        return jsonify({"success": False, "error": "Não foi possível importar a planilha."}), 400

@app.route("/lancamentos/novo", methods=["POST"])
def novo_lancamento():
    """Adiciona um novo lançamento avulso."""
    try:
        data_compra = request.form.get("data")
        descricao = request.form.get("descricao", "").strip()
        categoria = request.form.get("categoria")
        valor = parse_valor_localizado(request.form.get("valor", 0))
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
        valor = parse_valor_localizado(request.form.get("valor", 0))
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

    # Basear os totais nas parcelas ainda registradas, que podem ser excluídas por período.
    parcelas_registradas = [parcela for compra in compras for parcela in compra["parcelas"]]
    total_em_parcelas = sum(float(parcela["valor"]) for parcela in parcelas_registradas)
    total_ja_pago = sum(
        float(parcela["valor"])
        for parcela in parcelas_registradas
        if parcela["status"] == "Pago"
    )
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
        valor_total = parse_valor_localizado(request.form.get("valor_total", 0))
        entrada = parse_valor_localizado(request.form.get("entrada", 0))
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

@app.route("/parcelas/editar/<int:id>", methods=["POST"])
def editar_compra_parcelada(id):
    """Atualiza o cadastro de uma compra parcelada."""
    try:
        descricao = request.form.get("descricao", "").strip()
        data_compra = request.form.get("data_compra", "")
        valor_total = parse_valor_localizado(request.form.get("valor_total", 0))
        entrada = parse_valor_localizado(request.form.get("entrada", 0))
        num_parcelas = int(request.form.get("num_parcelas", 0))
        categoria = request.form.get("categoria", "")
        metodo = request.form.get("metodo_pagamento", "")
        cartao_id_texto = request.form.get("cartao_id", "")
        cartao_id = (
            int(cartao_id_texto)
            if cartao_id_texto and metodo == "Cartão de Crédito"
            else None
        )
        observacao = request.form.get("observacao", "").strip()

        categorias_validas = {
            item["categoria"] for item in models.get_limites_categoria()
        }
        if categoria not in categorias_validas:
            raise ValueError("Selecione uma categoria válida.")
        models.update_compra_parcelada(
            id, descricao, data_compra, valor_total, entrada, num_parcelas,
            categoria, metodo, cartao_id, observacao,
        )
        flash("Compra parcelada atualizada com sucesso.", "success")
    except (TypeError, ValueError) as erro:
        flash(f"Não foi possível atualizar a compra parcelada: {erro}", "danger")
    except Exception as erro:
        app.logger.exception("Erro ao atualizar compra parcelada %s", id)
        flash(f"Não foi possível atualizar a compra parcelada: {erro}", "danger")

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

@app.route("/parcelas/<int:id>/pagar", methods=["POST"])
def pagar_parcela(id):
    """Registra o pagamento mensal de uma parcela."""
    try:
        metodo = request.form.get("metodo_pagamento", "")
        cartao_id = request.form.get("cartao_id")
        cid = int(cartao_id) if cartao_id and metodo == "Cartão de Crédito" else None
        models.registrar_pagamento_parcela(id, metodo, cid)
        flash("Pagamento da parcela registrado nos lançamentos.", "success")
    except Exception as erro:
        flash(f"Não foi possível registrar o pagamento: {erro}", "danger")
    return redirect(request.referrer or url_for("parcelas"))

@app.route("/parcelas/<int:id>/desfazer-pagamento", methods=["POST"])
def desfazer_pagamento_parcela(id):
    """Reabre parcela paga e remove o lançamento gerado por ela."""
    try:
        models.desfazer_pagamento_parcela(id)
        flash("Pagamento desfeito; parcela voltou a ficar pendente.", "success")
    except Exception as erro:
        flash(f"Não foi possível desfazer o pagamento: {erro}", "danger")
    return redirect(request.referrer or url_for("parcelas"))

@app.route("/recorrentes")
def recorrentes():
    """Página anual de gerenciamento de gastos recorrentes e assinaturas."""
    hoje = date.today()
    try:
        ano = int(request.args.get("ano", hoje.year))
        if not 1 <= ano <= 9999:
            raise ValueError
    except ValueError:
        flash("Selecione um ano válido.", "danger")
        return redirect(url_for("recorrentes"))

    itens = models.get_gastos_recorrentes_ano(ano)
    total_anual_ativo = sum(
        float(item["valor_mensal"])
        * sum(
            1
            for mes in range(1, 13)
            if f"{ano:04d}-{mes:02d}" >= item["mes_inicio"]
            and item["status_meses"].get(
                f"{ano:04d}-{mes:02d}", {}
            ).get("ativo", bool(item["ativo_padrao"]))
        )
        for item in itens
    )

    return render_template(
        "recorrentes.html",
        recorrentes=itens,
        ano=ano,
        mes_inicio_padrao=hoje.strftime("%Y-%m"),
        meses=range(1, 13),
        total_anual_ativo=total_anual_ativo
    )

@app.route("/recorrentes/novo", methods=["POST"])
def novo_recorrente():
    """Cadastra novo gasto recorrente."""
    try:
        descricao = request.form.get("descricao", "").strip()
        valor_mensal = parse_valor_localizado(request.form.get("valor_mensal", 0))
        categoria = request.form.get("categoria")
        dia_cobranca = int(request.form.get("dia_cobranca", 5))
        metodo = request.form.get("metodo_pagamento")
        cartao_id = request.form.get("cartao_id")
        mes_inicio = request.form.get(
            "mes_inicio", date.today().strftime("%Y-%m")
        )

        cid = int(cartao_id) if cartao_id and metodo == "Cartão de Crédito" else None

        if not descricao or valor_mensal <= 0 or not 1 <= dia_cobranca <= 31:
            flash("Preencha a descrição, um valor positivo e um dia entre 1 e 31.", "danger")
            return redirect(url_for("recorrentes"))

        models.add_gasto_recorrente(
            descricao, valor_mensal, categoria, dia_cobranca, metodo, cid,
            mes_inicio,
        )
        flash(f"Gasto recorrente '{descricao}' adicionado com sucesso!", "success")
        return redirect(url_for("recorrentes", ano=mes_inicio[:4]))
    except Exception as e:
        flash(f"Erro ao salvar: {str(e)}", "danger")

    return redirect(url_for("recorrentes"))

@app.route("/recorrentes/editar/<int:id>", methods=["POST"])
def editar_recorrente(id):
    """Atualiza gasto recorrente."""
    try:
        descricao = request.form.get("descricao", "").strip()
        valor_mensal = parse_valor_localizado(request.form.get("valor_mensal", 0))
        categoria = request.form.get("categoria")
        dia_cobranca = int(request.form.get("dia_cobranca", 5))
        metodo = request.form.get("metodo_pagamento")
        cartao_id = request.form.get("cartao_id")

        if not descricao or valor_mensal <= 0 or not 1 <= dia_cobranca <= 31:
            raise ValueError("Preencha descrição, valor positivo e um dia entre 1 e 31.")
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

@app.route("/recorrentes/<int:id>/pagar", methods=["POST"])
def pagar_recorrente(id):
    """Registra o pagamento de uma recorrência no mês selecionado."""
    ano_mes = request.form.get("ano_mes", "")
    try:
        metodo = request.form.get("metodo_pagamento", "")
        cartao_id = request.form.get("cartao_id")
        cid = int(cartao_id) if cartao_id and metodo == "Cartão de Crédito" else None
        models.registrar_pagamento_recorrente(id, ano_mes, metodo, cid)
        flash("Pagamento recorrente registrado nos lançamentos.", "success")
    except Exception as erro:
        flash(f"Não foi possível registrar o pagamento: {erro}", "danger")
    return redirect(url_for("lancamentos"))

@app.route("/recorrentes/<int:id>/desfazer-pagamento", methods=["POST"])
def desfazer_pagamento_recorrente(id):
    """Reabre recorrência paga e remove o lançamento gerado por ela."""
    ano_mes = request.form.get("ano_mes", "")
    try:
        models.desfazer_pagamento_recorrente(id, ano_mes)
        flash("Pagamento desfeito; recorrência voltou a ficar pendente.", "success")
    except Exception as erro:
        flash(f"Não foi possível desfazer o pagamento: {erro}", "danger")
    try:
        ano = int(ano_mes[:4])
    except (TypeError, ValueError):
        ano = date.today().year
    return redirect(url_for("recorrentes", ano=ano))

@app.route("/cartoes")
def cartoes():
    """Página de múltiplos cartões de crédito com visualização de faturas e limites."""
    lista_cartoes = models.get_cartoes()
    hoje = date.today().strftime("%Y-%m")
    ano_mes = request.args.get("mes", hoje)
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", ano_mes):
        ano_mes = hoje

    # Detalhamento de cada cartão para o mês selecionado
    conn = database.get_db_connection()
    cursor = conn.cursor()

    for c in lista_cartoes:
        cid = c["id"]
        # Buscar compras avulsas desta fatura
        cursor.execute("""
            SELECT l.*, lim.cor as categoria_cor, lim.icone as categoria_icone
            FROM lancamentos l
            LEFT JOIN limites_categoria lim ON l.categoria = lim.categoria
            WHERE l.cartao_id = ? AND l.mes_vencimento = ?
            ORDER BY l.data DESC;
        """, (cid, ano_mes))
        c["itens_avulsos"] = [dict(r) for r in cursor.fetchall()]

        # Buscar parcelas desta fatura
        cursor.execute("""
            SELECT p.*, cp.descricao as compra_descricao, cp.categoria,
                   lim.cor as categoria_cor, lim.icone as categoria_icone
            FROM parcelas_detalhe p
            JOIN compras_parceladas cp ON p.compra_id = cp.id
            LEFT JOIN limites_categoria lim ON cp.categoria = lim.categoria
            WHERE cp.cartao_id = ? AND p.ano_mes = ? AND p.lancamento_id IS NULL
            ORDER BY p.data_vencimento ASC;
        """, (cid, ano_mes))
        c["itens_parcelas"] = [dict(r) for r in cursor.fetchall()]

        # Buscar assinaturas ativas neste cartão
        cursor.execute("""
            SELECT r.*, lim.cor as categoria_cor, lim.icone as categoria_icone,
                   COALESCE(s.ativo, r.ativo_padrao) as status_mes,
                   COALESCE(s.pago, 0) as pago, s.lancamento_id
            FROM gastos_recorrentes r
            LEFT JOIN recorrentes_status_mes s ON r.id = s.recorrente_id AND s.ano_mes = ?
            LEFT JOIN limites_categoria lim ON r.categoria = lim.categoria
            WHERE r.cartao_id = ?;
        """, (ano_mes, cid))
        c["itens_recorrentes"] = [
            dict(r) for r in cursor.fetchall()
            if r["status_mes"] == 1 and not r["lancamento_id"]
        ]

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
        limite_total = parse_valor_localizado(request.form.get("limite_total", 0))
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
        limite_total = parse_valor_localizado(request.form.get("limite_total", 0))
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
    config = models.get_configuracoes()
    try:
        ano = int(request.args.get("ano", config["ano_ativo"]))
        if not 1 <= ano <= 9999:
            raise ValueError("Informe um ano entre 1 e 9999.")
    except ValueError as erro:
        flash(f"Ano inválido: {erro}", "danger")
        return redirect(url_for("anual"))
    dados_ano = models.get_visao_anual(ano)

    return render_template(
        "anual.html",
        dados=dados_ano,
        ano=ano,
        cores_categorias={
            categoria["categoria"]: categoria["cor"]
            for categoria in models.get_limites_categoria()
        },
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
        cartoes=cartoes,
        data_formats={
            "dd/mm/aaaa": "dd/mm/aaaa",
            "extenso": "Dia de mês de ano",
            "semana_extenso": "Dia da semana, dia de mês de ano"
        },
        meses_nomes=[
            "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
            "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
        ],
    )

@app.route("/configuracoes/salvar", methods=["POST"])
def salvar_configuracoes():
    """Salva renda do ano selecionado, saldos e preferências de exibição."""
    try:
        ano = int(request.form.get("ano_ativo", date.today().year))
        if not 1 <= ano <= 9999:
            raise ValueError("Informe um ano válido.")
        modo_renda = request.form.get("modo_renda", "mensal")
        if modo_renda == "anual":
            salario = parse_valor_localizado(request.form.get("salario_anual", "0")) / 12
            outras_rendas = parse_valor_localizado(request.form.get("outras_rendas_anuais", "0")) / 12
        else:
            salario = parse_valor_localizado(request.form.get("salario_mensal", "0"))
            outras_rendas = parse_valor_localizado(request.form.get("outras_rendas_mensais", "0"))
        saldo_cc = parse_valor_localizado(request.form.get("saldo_conta_corrente", "0"))
        valor_investido = parse_valor_localizado(request.form.get("valor_investido", "0"))
        renda_variavel_mensal = request.form.get("renda_variavel_mensal") == "1"
        rendas_mensais = [
            {
                "salario": parse_valor_localizado(
                    request.form.get(f"salario_mes_{mes:02d}", salario)
                ),
                "outras_rendas": parse_valor_localizado(
                    request.form.get(f"outras_rendas_mes_{mes:02d}", outras_rendas)
                ),
            }
            for mes in range(1, 13)
        ]
        valores_renda = [salario, outras_rendas]
        valores_renda.extend(
            valor
            for renda in rendas_mensais
            for valor in renda.values()
        )
        if any(valor < 0 for valor in valores_renda):
            raise ValueError("Rendas devem ser iguais ou superiores a zero.")
        formato_data = request.form.get("formato_data", "dd/mm/aaaa")
        if formato_data not in {"dd/mm/aaaa", "extenso", "semana_extenso"}:
            raise ValueError("Selecione um formato de data válido.")

        models.update_configuracoes(
            salario, outras_rendas, saldo_cc, valor_investido, ano, formato_data,
            renda_variavel_mensal, rendas_mensais,
        )
        flash("Configurações e saldos atualizados com sucesso!", "success")
    except Exception as e:
        flash(f"Erro ao salvar configurações: {str(e)}", "danger")

    return redirect(url_for("configuracoes"))

@app.route("/configuracoes/ano", methods=["POST"])
def salvar_ano_ativo():
    """Salva o ano de referência para o dashboard e para a renda anual."""
    try:
        ano = int(request.form.get("ano_ativo", ""))
        if not 1 <= ano <= 9999:
            raise ValueError("Informe um ano entre 1 e 9999.")
        models.update_ano_ativo(ano)
        flash(f"Ano de referência alterado para {ano}.", "success")
    except (TypeError, ValueError) as erro:
        flash(f"Não foi possível alterar o ano: {erro}", "danger")
    return redirect(url_for("configuracoes"))

@app.route("/configuracoes/saldos", methods=["POST"])
def salvar_saldos_rapido():
    """Ajuste rápido de saldos (utilizado no modal do cabeçalho)."""
    try:
        saldo_cc = parse_valor_localizado(request.form.get("saldo_conta_corrente", 0))
        valor_investido = parse_valor_localizado(request.form.get("valor_investido", 0))

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
        novos_limites = []
        for l in limites:
            cat = l["categoria"]
            campo = f"limite_{cat}"
            if campo in request.form:
                novo_limite = parse_valor_localizado(request.form.get(campo, 0))
                if novo_limite < 0:
                    raise ValueError("Os limites devem ser iguais ou superiores a zero.")
                novos_limites.append((cat, novo_limite))
        for cat, novo_limite in novos_limites:
            models.update_limite_categoria(cat, novo_limite)

        flash("Limites por categoria atualizados com sucesso!", "success")
    except Exception as e:
        flash(f"Erro ao atualizar limites: {str(e)}", "danger")

    return redirect(url_for("configuracoes"))

@app.route("/configuracoes/excluir-dados", methods=["POST"])
def excluir_dados():
    """Remove movimentações de um período ou limpa todos os dados financeiros."""
    tipo = request.form.get("tipo", "")
    try:
        if tipo == "todos":
            if request.form.get("confirmacao", "").strip() != "EXCLUIR TUDO":
                raise ValueError("Digite EXCLUIR TUDO para confirmar a limpeza completa.")
            models.excluir_todos_dados()
            flash(
                "Todos os dados financeiros foram excluídos. "
                "Saldos e rendas foram zerados; categorias padrão foram restauradas.",
                "success",
            )
        elif tipo in {"dia", "semana", "mes", "ano"}:
            resultado = models.excluir_dados_periodo(
                tipo, request.form.get("referencia", "")
            )
            contexto_data = {
                "global_config": {
                    "formato_data": models.get_configuracoes()["formato_data"]
                }
            }
            periodo = (
                filter_data_br(contexto_data, resultado["inicio"].isoformat())
                if resultado["inicio"] == resultado["fim"]
                else f"{filter_data_br(contexto_data, resultado['inicio'].isoformat())} a "
                     f"{filter_data_br(contexto_data, resultado['fim'].isoformat())}"
            )
            flash(
                f"Exclusão concluída para {periodo}: "
                f"{resultado['lancamentos']} lançamento(s) e "
                f"{resultado['parcelas']} parcela(s) removidos.",
                "success",
            )
        else:
            raise ValueError("Selecione um tipo de período válido.")
    except ValueError as erro:
        flash(str(erro), "danger")
    except Exception:
        app.logger.exception("Erro ao excluir dados financeiros")
        flash("Não foi possível excluir os dados. Nenhuma alteração foi confirmada.", "danger")

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
            "data_vencimento_formatada": filter_data_br(
                {"global_config": models.get_configuracoes()}, data_venc
            ),
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
