import sqlite3
import os
import json
from datetime import datetime, date
import calendar

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Dados", "finance.db")

CATEGORIAS_PADRAO = [
    ("Moradia", 1800.0, "bi-house-door", "#4f46e5"),
    ("Alimentação", 1200.0, "bi-egg-fried", "#f59e0b"),
    ("Transporte", 500.0, "bi-car-front", "#06b6d4"),
    ("Educação", 400.0, "bi-mortarboard", "#8b5cf6"),
    ("Saúde", 350.0, "bi-heart-pulse", "#ef4444"),
    ("Lazer", 450.0, "bi-controller", "#ec4899"),
    ("Vestuário", 250.0, "bi-handbag", "#14b8a6"),
    ("Tecnologia", 300.0, "bi-laptop", "#3b82f6"),
    ("Pessoal", 200.0, "bi-person", "#f97316"),
    ("Viagens", 500.0, "bi-airplane", "#10b981"),
    ("Outros", 200.0, "bi-tags", "#6b7280"),
]

def get_db_connection():
    """Retorna uma conexão SQLite configurada com suporte a dicionários."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    """Inicializa as tabelas do banco de dados SQLite caso não existam."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Configurações gerais e saldos de patrimônio
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS configuracoes (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            salario REAL NOT NULL DEFAULT 4500.0,
            outras_rendas REAL NOT NULL DEFAULT 500.0,
            saldo_conta_corrente REAL NOT NULL DEFAULT 0.0,
            valor_investido REAL NOT NULL DEFAULT 0.0,
            data_atualizacao TEXT
        );
    """)

    # Migrar colunas de preferências de forma compatível com bancos existentes.
    colunas_config = {
        row["name"] for row in cursor.execute("PRAGMA table_info(configuracoes);")
    }
    if "ano_ativo" not in colunas_config:
        cursor.execute("ALTER TABLE configuracoes ADD COLUMN ano_ativo INTEGER;")
    if "formato_data" not in colunas_config:
        cursor.execute(
            "ALTER TABLE configuracoes ADD COLUMN formato_data TEXT NOT NULL DEFAULT 'dd/mm/aaaa';"
        )
    cursor.execute("""
        UPDATE configuracoes
        SET ano_ativo = CAST(strftime('%Y', 'now', 'localtime') AS INTEGER)
        WHERE ano_ativo IS NULL OR ano_ativo < 1;
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rendas_anuais (
            ano INTEGER PRIMARY KEY CHECK (ano BETWEEN 1 AND 9999),
            salario_mensal REAL NOT NULL DEFAULT 0.0,
            outras_rendas_mensais REAL NOT NULL DEFAULT 0.0,
            data_atualizacao TEXT
        );
    """)
    cursor.execute("""
        INSERT OR IGNORE INTO rendas_anuais
            (ano, salario_mensal, outras_rendas_mensais, data_atualizacao)
        SELECT ano_ativo, salario, outras_rendas, data_atualizacao
        FROM configuracoes WHERE id = 1;
    """)

    # 2. Limites por categoria
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS limites_categoria (
            categoria TEXT PRIMARY KEY,
            limite_mensal REAL NOT NULL DEFAULT 0.0,
            icone TEXT DEFAULT 'bi-tag',
            cor TEXT DEFAULT '#6b7280'
        );
    """)

    # 3. Cartões de Crédito
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cartoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            limite_total REAL NOT NULL DEFAULT 0.0,
            fechamento_dia INTEGER NOT NULL CHECK (fechamento_dia BETWEEN 1 AND 31),
            vencimento_dia INTEGER NOT NULL CHECK (vencimento_dia BETWEEN 1 AND 31),
            cor TEXT DEFAULT '#3b82f6',
            bandeira TEXT DEFAULT 'Mastercard',
            ativo INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 4. Lançamentos Avulsos (Gastos Diários)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lancamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,               -- YYYY-MM-DD
            ano_mes TEXT NOT NULL,           -- YYYY-MM (mês da compra)
            descricao TEXT NOT NULL,
            categoria TEXT NOT NULL,
            valor REAL NOT NULL,
            observacao TEXT,
            metodo_pagamento TEXT NOT NULL,   -- Cartão de Débito, Pix, Dinheiro ou Cartão de Crédito
            cartao_id INTEGER REFERENCES cartoes(id) ON DELETE SET NULL,
            fatura_mes TEXT,                  -- YYYY-MM (mês de fechamento/competência da fatura)
            mes_vencimento TEXT,             -- YYYY-MM (mês em que a fatura vence e deve ser paga)
            data_vencimento TEXT,            -- YYYY-MM-DD data exata de vencimento
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)
    # 5. Compras Parceladas (Cabeçalho)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS compras_parceladas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            descricao TEXT NOT NULL,
            data_compra TEXT NOT NULL,        -- YYYY-MM-DD
            valor_total REAL NOT NULL,
            entrada REAL NOT NULL DEFAULT 0.0,
            num_parcelas INTEGER NOT NULL CHECK (num_parcelas >= 1),
            valor_parcela REAL NOT NULL,
            categoria TEXT NOT NULL,
            metodo_pagamento TEXT NOT NULL,
            cartao_id INTEGER REFERENCES cartoes(id) ON DELETE SET NULL,
            mes_inicio TEXT NOT NULL,         -- YYYY-MM da primeira parcela/fatura
            mes_fim TEXT NOT NULL,            -- YYYY-MM da última parcela/fatura
            observacao TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 6. Detalhe das Parcelas (Projeção mensal)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS parcelas_detalhe (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            compra_id INTEGER NOT NULL REFERENCES compras_parceladas(id) ON DELETE CASCADE,
            numero_parcela INTEGER NOT NULL,
            total_parcelas INTEGER NOT NULL,
            ano_mes TEXT NOT NULL,            -- YYYY-MM do vencimento/fatura desta parcela
            valor REAL NOT NULL,
            data_vencimento TEXT,             -- YYYY-MM-DD
            status TEXT DEFAULT 'Pendente'    -- 'Pendente', 'Pago'
        );
    """)

    # 7. Gastos Recorrentes (Assinaturas e Contas Fixas)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gastos_recorrentes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            descricao TEXT NOT NULL,
            valor_mensal REAL NOT NULL,
            categoria TEXT NOT NULL,
            dia_cobranca INTEGER DEFAULT 5,
            metodo_pagamento TEXT DEFAULT 'Cartão de Débito',
            cartao_id INTEGER REFERENCES cartoes(id) ON DELETE SET NULL,
            ativo_padrao INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 8. Status mensal de gastos recorrentes (Permitir pausar/ativar por mês específico)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recorrentes_status_mes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recorrente_id INTEGER NOT NULL REFERENCES gastos_recorrentes(id) ON DELETE CASCADE,
            ano_mes TEXT NOT NULL,            -- YYYY-MM
            ativo INTEGER NOT NULL,           -- 1 = Ativo, 0 = Pausado
            UNIQUE(recorrente_id, ano_mes)
        );
    """)
    cursor.execute("""
        UPDATE lancamentos SET metodo_pagamento = 'Cartão de Débito'
        WHERE metodo_pagamento = 'Conta Corrente';
    """)
    cursor.execute("""
        UPDATE gastos_recorrentes SET metodo_pagamento = 'Cartão de Débito'
        WHERE metodo_pagamento = 'Conta Corrente';
    """)

    # Inicializar registro de configurações se vazio
    cursor.execute("SELECT COUNT(*) FROM configuracoes;")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT INTO configuracoes (id, salario, outras_rendas, saldo_conta_corrente, valor_investido, data_atualizacao)
            VALUES (1, 4500.0, 500.0, 3250.0, 25400.0, datetime('now', 'localtime'));
        """)
    cursor.execute("""
        UPDATE configuracoes
        SET ano_ativo = CAST(strftime('%Y', 'now', 'localtime') AS INTEGER)
        WHERE id = 1 AND (ano_ativo IS NULL OR ano_ativo < 1);
    """)
    cursor.execute("""
        INSERT OR IGNORE INTO rendas_anuais
            (ano, salario_mensal, outras_rendas_mensais, data_atualizacao)
        SELECT ano_ativo, salario, outras_rendas, data_atualizacao
        FROM configuracoes WHERE id = 1;
    """)

    # Inicializar ou atualizar categorias padrão com cores distintas e vibrantes
    for cat, lim, icon, color in CATEGORIAS_PADRAO:
        cursor.execute("""
            INSERT INTO limites_categoria (categoria, limite_mensal, icone, cor)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(categoria) DO UPDATE SET icone = excluded.icone, cor = excluded.cor;
        """, (cat, lim, icon, color))

    conn.commit()
    conn.close()

def add_months(sourcedate, months):
    """Adiciona 'months' meses a uma data preservando o dia de forma segura."""
    month = sourcedate.month - 1 + months
    year = sourcedate.year + month // 12
    month = month % 12 + 1
    day = min(sourcedate.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)

def calcular_fatura_e_vencimento(data_compra_str, fechamento_dia, vencimento_dia):
    """
    Calcula:
    - fatura_mes: YYYY-MM ciclo de fechamento
    - mes_vencimento: YYYY-MM em que a fatura vence para pagamento
    - data_vencimento: YYYY-MM-DD
    
    Regra de Fatura: Se a data de uma compra em cartão de crédito for posterior ou igual
    ao dia de fechamento do cartão no mês atual, a despesa deve ser alocada na fatura do mês seguinte.
    """
    compra_date = datetime.strptime(data_compra_str, "%Y-%m-%d").date()
    ano = compra_date.year
    mes = compra_date.month
    dia = compra_date.day

    # Se a compra for feita a partir do dia de fechamento, cai no ciclo seguinte
    if dia >= fechamento_dia:
        fatura_date = add_months(date(ano, mes, 1), 1)
    else:
        fatura_date = date(ano, mes, 1)

    fatura_mes = fatura_date.strftime("%Y-%m")

    # Mês do vencimento:
    # Se vencimento_dia > fechamento_dia, vence no mesmo mês do fechamento
    # Se vencimento_dia <= fechamento_dia, vence no mês subsequente
    if vencimento_dia > fechamento_dia:
        venc_date = fatura_date
    else:
        venc_date = add_months(fatura_date, 1)

    venc_ano = venc_date.year
    venc_mes = venc_date.month
    max_day = calendar.monthrange(venc_ano, venc_mes)[1]
    venc_dia_real = min(vencimento_dia, max_day)

    data_vencimento = date(venc_ano, venc_mes, venc_dia_real).strftime("%Y-%m-%d")
    mes_vencimento = date(venc_ano, venc_mes, 1).strftime("%Y-%m")

    return fatura_mes, mes_vencimento, data_vencimento

def gerar_parcelas_compra(cursor, compra_id, data_compra_str, valor_total, entrada, num_parcelas, cartao_id=None):
    """Gera a projeção cronológica de parcelas detalhadas de uma compra parcelada."""
    valor_financ = valor_total - entrada
    if num_parcelas <= 0:
        num_parcelas = 1
    valor_parcela = round(valor_financ / num_parcelas, 2)

    # Buscar dados do cartão se houver
    fechamento_dia = None
    vencimento_dia = None
    if cartao_id:
        cursor.execute("SELECT fechamento_dia, vencimento_dia FROM cartoes WHERE id = ?", (cartao_id,))
        row = cursor.fetchone()
        if row:
            fechamento_dia = row["fechamento_dia"]
            vencimento_dia = row["vencimento_dia"]

    cursor.execute("DELETE FROM parcelas_detalhe WHERE compra_id = ?", (compra_id,))

    compra_date = datetime.strptime(data_compra_str, "%Y-%m-%d").date()

    for i in range(1, num_parcelas + 1):
        # A data base de cada parcela avança mês a mês
        parcela_base_date = add_months(compra_date, i - 1)
        parcela_base_str = parcela_base_date.strftime("%Y-%m-%d")

        if fechamento_dia and vencimento_dia:
            fatura_mes, mes_venc, data_venc = calcular_fatura_e_vencimento(parcela_base_str, fechamento_dia, vencimento_dia)
            mes_alocacao = mes_venc
        else:
            # Sem cartão (boleto, carnê etc): primeira parcela no mês da compra ou subsequente
            mes_alocacao = parcela_base_date.strftime("%Y-%m")
            data_venc = parcela_base_str

        # Ajuste de centavos na última parcela para totalizar exatamente valor_financ
        if i == num_parcelas:
            parcela_val = round(valor_financ - (valor_parcela * (num_parcelas - 1)), 2)
        else:
            parcela_val = valor_parcela

        cursor.execute("""
            INSERT INTO parcelas_detalhe (compra_id, numero_parcela, total_parcelas, ano_mes, valor, data_vencimento, status)
            VALUES (?, ?, ?, ?, ?, ?, 'Pendente');
        """, (compra_id, i, num_parcelas, mes_alocacao, parcela_val, data_venc))

def popular_dados_exemplo():
    """Popula o banco de dados com um conjunto rico e realista de dados de exemplo."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()

    # Resetar dados operacionais para teste limpo
    cursor.execute("DELETE FROM lancamentos;")
    cursor.execute("DELETE FROM parcelas_detalhe;")
    cursor.execute("DELETE FROM compras_parceladas;")
    cursor.execute("DELETE FROM recorrentes_status_mes;")
    cursor.execute("DELETE FROM gastos_recorrentes;")
    cursor.execute("DELETE FROM cartoes;")

    # 1. Configurações
    cursor.execute("""
        UPDATE configuracoes 
        SET salario = 6500.0, outras_rendas = 800.0, saldo_conta_corrente = 4250.80, valor_investido = 32800.0,
            data_atualizacao = datetime('now', 'localtime')
        WHERE id = 1;
    """)

    # 2. Cartões
    cartoes_demo = [
        ("Nubank Ultravioleta", 9000.0, 25, 5, "#820ad1", "Mastercard"),
        ("XP Visa Infinite", 15000.0, 18, 28, "#1a1a1a", "Visa"),
        ("Itaú Click", 4500.0, 10, 20, "#ec7000", "Mastercard")
    ]
    cartao_ids = {}
    for nome, lim, fech, venc, cor, band in cartoes_demo:
        cursor.execute("""
            INSERT INTO cartoes (nome, limite_total, fechamento_dia, vencimento_dia, cor, bandeira)
            VALUES (?, ?, ?, ?, ?, ?);
        """, (nome, lim, fech, venc, cor, band))
        cartao_ids[nome] = cursor.lastrowid

    hoje = date.today()
    ano_atual = hoje.year
    mes_atual = hoje.month
    mes_atual_str = hoje.strftime("%Y-%m")

    # Mês anterior e mês seguinte
    mes_ant = add_months(hoje, -1)
    mes_ant_str = mes_ant.strftime("%Y-%m")
    mes_seg = add_months(hoje, 1)
    mes_seg_str = mes_seg.strftime("%Y-%m")

    # 3. Lançamentos avulsos
    lancamentos_demo = [
        # Data, Descricao, Categoria, Valor, Metodo, CartaoNome, Obs
        (f"{mes_atual_str}-02", "Supermercado Pão de Açúcar", "Alimentação", 342.50, "Cartão de Crédito", "Nubank Ultravioleta", "Compras do mês"),
        (f"{mes_atual_str}-05", "Posto Ipiranga - Gasolina", "Transporte", 220.00, "Pix", None, "Tanque cheio"),
        (f"{mes_atual_str}-07", "Farmácia Droga Raia", "Saúde", 94.20, "Cartão de Crédito", "Nubank Ultravioleta", "Medicamentos"),
        (f"{mes_atual_str}-10", "Almoço Restaurante Bistrô", "Alimentação", 78.00, "Cartão de Crédito", "XP Visa Infinite", "Almoço com colegas"),
        (f"{mes_atual_str}-12", "Livros e Cursos Online", "Educação", 149.90, "Cartão de Crédito", "XP Visa Infinite", "Curso Python Avançado"),
        (f"{mes_atual_str}-15", "Cinema e Pipoca", "Lazer", 85.00, "Pix", None, "Filme fim de semana"),
        (f"{mes_atual_str}-18", "Roupas Zara", "Vestuário", 219.00, "Cartão de Crédito", "Itaú Click", "Camisa e calça"),
        (f"{mes_atual_str}-20", "Acessórios para Celular", "Tecnologia", 89.90, "Cartão de Crédito", "Nubank Ultravioleta", "Cabo e capa"),
        (f"{mes_atual_str}-22", "Supermercado Extra", "Alimentação", 285.30, "Cartão de Crédito", "Nubank Ultravioleta", "Reposição hortifruti"),
        (f"{mes_atual_str}-26", "Cafeteria Especial", "Lazer", 45.00, "Dinheiro", None, "Café com sobremesa"),
        (f"{mes_atual_str}-27", "Compra pós-fechamento Nubank", "Outros", 150.00, "Cartão de Crédito", "Nubank Ultravioleta", "Teste regra fechamento fatura"),
        
        # Mês anterior
        (f"{mes_ant_str}-03", "Supermercado Carrefour", "Alimentação", 412.00, "Cartão de Crédito", "Nubank Ultravioleta", "Compras quinzenais"),
        (f"{mes_ant_str}-08", "Uber e Metrô", "Transporte", 135.40, "Cartão de Débito", None, "Deslocamentos urbanos"),
        (f"{mes_ant_str}-14", "Jantar Japonês", "Alimentação", 195.00, "Cartão de Crédito", "XP Visa Infinite", "Comemoração"),
        (f"{mes_ant_str}-20", "Exames Médicos Laboratório", "Saúde", 180.00, "Pix", None, "Check-up de rotina")
    ]

    for dt, desc, cat, val, met, c_nome, obs in lancamentos_demo:
        cid = cartao_ids.get(c_nome) if c_nome else None
        fat_mes, mes_venc, data_venc = None, None, None
        ano_mes = dt[:7]
        if cid:
            cursor.execute("SELECT fechamento_dia, vencimento_dia FROM cartoes WHERE id = ?", (cid,))
            crow = cursor.fetchone()
            fat_mes, mes_venc, data_venc = calcular_fatura_e_vencimento(dt, crow["fechamento_dia"], crow["vencimento_dia"])
        else:
            mes_venc = ano_mes
            data_venc = dt

        cursor.execute("""
            INSERT INTO lancamentos (data, ano_mes, descricao, categoria, valor, observacao, metodo_pagamento, cartao_id, fatura_mes, mes_vencimento, data_vencimento)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (dt, ano_mes, desc, cat, val, obs, met, cid, fat_mes, mes_venc, data_venc))

    # 4. Compras Parceladas
    compras_demo = [
        ("Notebook Dell Inspiron", f"{mes_ant_str}-10", 4500.0, 500.0, 10, "Tecnologia", "Cartão de Crédito", cartao_ids["XP Visa Infinite"], "Trabalho e estudos"),
        ("Passagens Aéreas Férias", f"{mes_atual_str}-05", 1800.0, 0.0, 6, "Viagens", "Cartão de Crédito", cartao_ids["Nubank Ultravioleta"], "Viagem final de ano"),
        ("Smartphone Galaxy", f"{mes_ant_str}-22", 2400.0, 400.0, 5, "Tecnologia", "Cartão de Crédito", cartao_ids["Itaú Click"], "Troca de celular")
    ]

    for desc, dt_compra, v_tot, ent, n_parc, cat, met, cid, obs in compras_demo:
        v_parc = round((v_tot - ent) / n_parc, 2)
        # Obter mes_inicio e mes_fim
        cursor.execute("SELECT fechamento_dia, vencimento_dia FROM cartoes WHERE id = ?", (cid,))
        crow = cursor.fetchone()
        _, mes_ini, _ = calcular_fatura_e_vencimento(dt_compra, crow["fechamento_dia"], crow["vencimento_dia"])
        dt_fim = add_months(datetime.strptime(mes_ini + "-01", "%Y-%m-%d").date(), n_parc - 1)
        mes_fim = dt_fim.strftime("%Y-%m")

        cursor.execute("""
            INSERT INTO compras_parceladas (descricao, data_compra, valor_total, entrada, num_parcelas, valor_parcela, categoria, metodo_pagamento, cartao_id, mes_inicio, mes_fim, observacao)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (desc, dt_compra, v_tot, ent, n_parc, v_parc, cat, met, cid, mes_ini, mes_fim, obs))
        compra_id = cursor.lastrowid
        gerar_parcelas_compra(cursor, compra_id, dt_compra, v_tot, ent, n_parc, cid)

    # 5. Gastos Recorrentes
    recorrentes_demo = [
        ("Aluguel do Apartamento", 1500.0, "Moradia", 5, "Cartão de Débito", None),
        ("Condomínio Residencial", 420.0, "Moradia", 10, "Cartão de Débito", None),
        ("Internet Fibra 500MB", 129.90, "Moradia", 15, "Pix", None),
        ("Assinatura Netflix Premium", 55.90, "Lazer", 20, "Cartão de Crédito", cartao_ids["Nubank Ultravioleta"]),
        ("Spotify Familiar", 34.90, "Lazer", 12, "Cartão de Crédito", cartao_ids["Nubank Ultravioleta"]),
        ("Plano de Saúde", 320.00, "Saúde", 8, "Cartão de Débito", None),
        ("Academia Smart Fit", 119.90, "Saúde", 1, "Cartão de Crédito", cartao_ids["XP Visa Infinite"])
    ]

    for desc, val, cat, dia, met, cid in recorrentes_demo:
        cursor.execute("""
            INSERT INTO gastos_recorrentes (descricao, valor_mensal, categoria, dia_cobranca, metodo_pagamento, cartao_id, ativo_padrao)
            VALUES (?, ?, ?, ?, ?, ?, 1);
        """, (desc, val, cat, dia, met, cid))

    conn.commit()
    conn.close()
    return True

if __name__ == "__main__":
    init_db()
    popular_dados_exemplo()
    print("Banco de dados SQLite inicializado com sucesso!")
