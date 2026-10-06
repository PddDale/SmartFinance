import json
import os
import tempfile
import unittest
from datetime import date
from unittest.mock import patch

from Recursos.Codigo.app import app
from Recursos.Codigo import database


class TestSmartFinance(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_01_index_dashboard(self):
        response = self.app.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"SmartFinance", response.data)
        self.assertIn(b"Resumo Financeiro", response.data)
        self.assertIn(b"Patrim", response.data)
        self.assertIn(b"Limite e Uso por Categoria", response.data)
        self.assertIn(b"Porcentagem de uso:", response.data)
        self.assertIn(b"Gasto atual:", response.data)
        self.assertIn(b"Meta:", response.data)
        self.assertIn(b"Acima do limite:", response.data)
        self.assertIn(b"R$ ", response.data)

    def test_02_lancamentos_page(self):
        response = self.app.get("/lancamentos")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"SmartFinance", response.data)
        self.assertIn(b"Gastos", response.data)

    def test_03_parcelas_page(self):
        response = self.app.get("/parcelas")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"SmartFinance", response.data)
        self.assertIn(b"Compras Parceladas", response.data)

    def test_04_recorrentes_page(self):
        response = self.app.get("/recorrentes")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"SmartFinance", response.data)
        self.assertIn(b"Gastos Recorrentes", response.data)

    def test_05_cartoes_page(self):
        response = self.app.get("/cartoes")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"SmartFinance", response.data)
        self.assertIn(b"Cart", response.data)

    def test_06_anual_page(self):
        response = self.app.get("/anual")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"SmartFinance", response.data)
        self.assertIn(b"Vis", response.data)

    def test_07_configuracoes_page(self):
        response = self.app.get("/configuracoes")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"SmartFinance", response.data)
        self.assertIn(b"Configura", response.data)

    def test_08_api_calcular_fatura(self):
        conn = database.get_db_connection()
        cartao = conn.execute("SELECT id FROM cartoes LIMIT 1;").fetchone()
        conn.close()
        self.assertIsNotNone(cartao)

        response = self.app.post(
            "/api/calcular-fatura",
            data=json.dumps({"data": "2026-10-26", "cartao_id": cartao["id"]}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["success"])
        self.assertIn("fatura_mes", data)
        self.assertIn("data_vencimento", data)

    def test_09_exportar_json(self):
        response = self.app.get("/configuracoes/exportar-json")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn("configuracoes", data)
        self.assertIn("rendas_anuais", data["configuracoes"])
        self.assertIn("saldos", data)
        self.assertIn("cartoes", data)
        self.assertIn("lancamentos", data)

    def test_10_novo_lancamento_and_delete(self):
        response = self.app.post(
            "/lancamentos/novo",
            data={
                "data": "2026-10-05",
                "descricao": "Teste Automatizado Lanche",
                "categoria": "Alimentação",
                "valor": "35,50",
                "metodo_pagamento": "Pix",
                "observacao": "Teste unitário",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Teste Automatizado Lanche", response.data)

        conn = database.get_db_connection()
        row = conn.execute(
            "SELECT id FROM lancamentos WHERE descricao = 'Teste Automatizado Lanche';"
        ).fetchone()
        conn.close()
        self.assertIsNotNone(row)

        response = self.app.post(
            f"/lancamentos/excluir/{row['id']}", follow_redirects=True
        )
        self.assertEqual(response.status_code, 200)

    @patch("os._exit")
    def test_11_api_encerrar(self, mock_exit):
        response = self.app.post("/api/encerrar")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["success"])
        self.assertIn("SmartFinance", data["message"])

    def test_12_api_categorizar_regras(self):
        casos = [
            ("iFood almoço executivo", "Alimentação"),
            ("Uber corrida aeroporto", "Transporte"),
            ("Netflix assinatura mensal", "Lazer"),
            ("Drogasil remédio pressão", "Saúde"),
            ("Conta de luz CEMIG", "Moradia"),
        ]
        for descricao, categoria_esperada in casos:
            with self.subTest(descricao=descricao):
                response = self.app.post(
                    "/api/categorizar",
                    data=json.dumps({"descricao": descricao}),
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 200)
                data = json.loads(response.data)
                self.assertTrue(data["success"])
                self.assertEqual(data["categoria"], categoria_esperada)

    def test_13_api_categorizar_historico(self):
        self.app.post(
            "/lancamentos/novo",
            data={
                "data": "2026-10-01",
                "descricao": "Mercadinho do Zé",
                "categoria": "Alimentação",
                "valor": "50.00",
                "metodo_pagamento": "Pix",
            },
        )
        response = self.app.post(
            "/api/categorizar",
            data=json.dumps({"descricao": "Mercadinho do Zé"}),
            content_type="application/json",
        )
        data = json.loads(response.data)
        self.assertTrue(data["success"])
        self.assertEqual(data["categoria"], "Alimentação")

        conn = database.get_db_connection()
        conn.execute("DELETE FROM lancamentos WHERE descricao='Mercadinho do Zé';")
        conn.commit()
        conn.close()

    def test_14_renda_anual_e_preferencias_persistem_por_ano(self):
        with tempfile.TemporaryDirectory() as pasta:
            with patch.object(
                database, "DB_PATH", os.path.join(pasta, "finance.db")
            ):
                database.init_db()
                conn = database.get_db_connection()
                config_inicial = conn.execute(
                    "SELECT ano_ativo FROM configuracoes WHERE id = 1;"
                ).fetchone()
                conn.close()
                self.assertEqual(config_inicial["ano_ativo"], date.today().year)

                response = self.app.post(
                    "/configuracoes/salvar",
                    data={
                        "ano_ativo": "2032",
                        "modo_renda": "anual",
                        "salario_anual": "120000",
                        "outras_rendas_anuais": "24000",
                        "saldo_conta_corrente": "2500",
                        "valor_investido": "15000",
                        "formato_data": "semana_extenso",
                    },
                )
                self.assertEqual(response.status_code, 302)

                conn = database.get_db_connection()
                config = conn.execute(
                    "SELECT ano_ativo, formato_data FROM configuracoes WHERE id = 1;"
                ).fetchone()
                renda = conn.execute(
                    "SELECT salario_mensal, outras_rendas_mensais "
                    "FROM rendas_anuais WHERE ano = 2032;"
                ).fetchone()
                conn.close()
                self.assertEqual(config["ano_ativo"], 2032)
                self.assertEqual(config["formato_data"], "semana_extenso")
                self.assertEqual(renda["salario_mensal"], 10000)
                self.assertEqual(renda["outras_rendas_mensais"], 2000)

                response = self.app.get("/")
                dias = [
                    "segunda-feira",
                    "terça-feira",
                    "quarta-feira",
                    "quinta-feira",
                    "sexta-feira",
                    "sábado",
                    "domingo",
                ]
                trecho_data = (
                    f"{dias[date.today().weekday()]}, {date.today().day} de "
                )
                self.assertIn(trecho_data.encode("utf-8"), response.data)

                self.app.post("/configuracoes/ano", data={"ano_ativo": "2033"})
                conn = database.get_db_connection()
                renda_ano_novo = conn.execute(
                    "SELECT ano FROM rendas_anuais WHERE ano = 2033;"
                ).fetchone()
                conn.close()
                self.assertIsNotNone(renda_ano_novo)

    def test_15_recursos_estaticos_e_banco_local(self):
        css = self.app.get("/static/css/style.css")
        js = self.app.get("/static/js/app.js")
        try:
            self.assertEqual(css.status_code, 200)
            self.assertEqual(js.status_code, 200)
        finally:
            css.close()
            js.close()
        self.assertTrue(
            database.DB_PATH.endswith(
                os.path.join("Recursos", "Dados", "finance.db")
            )
        )

    def test_16_exclusao_por_periodo_preserva_cadastros_e_outras_parcelas(self):
        with tempfile.TemporaryDirectory() as pasta:
            with patch.object(
                database, "DB_PATH", os.path.join(pasta, "finance.db")
            ):
                database.init_db()
                conn = database.get_db_connection()
                cartao_id = conn.execute("""
                    INSERT INTO cartoes
                        (nome, limite_total, fechamento_dia, vencimento_dia)
                    VALUES ('Cartão de teste', 1000, 10, 20);
                """).lastrowid
                compra_id = conn.execute("""
                    INSERT INTO compras_parceladas (
                        descricao, data_compra, valor_total, entrada, num_parcelas,
                        valor_parcela, categoria, metodo_pagamento, cartao_id,
                        mes_inicio, mes_fim
                    ) VALUES (
                        'Compra de teste', '2026-10-01', 300, 0, 3, 100,
                        'Outros', 'Cartão de Crédito', ?, '2026-10', '2026-12'
                    );
                """, (cartao_id,)).lastrowid
                conn.executemany("""
                    INSERT INTO parcelas_detalhe (
                        compra_id, numero_parcela, total_parcelas, ano_mes,
                        valor, data_vencimento, status
                    ) VALUES (?, ?, 3, ?, 100, ?, 'Pendente');
                """, [
                    (compra_id, 1, "2026-10", "2026-10-05"),
                    (compra_id, 2, "2026-11", "2026-11-05"),
                ])
                conn.executemany("""
                    INSERT INTO lancamentos (
                        data, ano_mes, descricao, categoria, valor, metodo_pagamento
                    ) VALUES (?, ?, ?, 'Outros', 10, 'Pix');
                """, [
                    ("2026-10-05", "2026-10", "Excluir"),
                    ("2026-10-06", "2026-10", "Preservar"),
                ])
                conn.execute("""
                    INSERT INTO gastos_recorrentes (descricao, valor_mensal, categoria)
                    VALUES ('Assinatura de teste', 20, 'Outros');
                """)
                conn.execute("""
                    UPDATE configuracoes
                    SET saldo_conta_corrente = 1234, valor_investido = 5678
                    WHERE id = 1;
                """)
                conn.commit()
                conn.close()

                response = self.app.post(
                    "/configuracoes/excluir-dados",
                    data={"tipo": "dia", "referencia": "data-invalida"},
                )
                self.assertEqual(response.status_code, 302)

                response = self.app.post(
                    "/configuracoes/excluir-dados",
                    data={"tipo": "dia", "referencia": "2026-10-05"},
                )
                self.assertEqual(response.status_code, 302)

                conn = database.get_db_connection()
                self.assertEqual(
                    [tuple(row) for row in conn.execute(
                        "SELECT descricao FROM lancamentos;"
                    ).fetchall()],
                    [("Preservar",)],
                )
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM parcelas_detalhe;").fetchone()[0],
                    1,
                )
                self.assertIsNotNone(conn.execute(
                    "SELECT id FROM compras_parceladas WHERE id = ?;", (compra_id,)
                ).fetchone())
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM cartoes;").fetchone()[0], 1)
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM gastos_recorrentes;").fetchone()[0],
                    1,
                )
                config = conn.execute(
                    "SELECT saldo_conta_corrente, valor_investido "
                    "FROM configuracoes WHERE id = 1;"
                ).fetchone()
                conn.close()
                self.assertEqual(tuple(config), (1234, 5678))

    def test_17_exclusao_total_apaga_dados_e_zera_saldos(self):
        with tempfile.TemporaryDirectory() as pasta:
            with patch.object(
                database, "DB_PATH", os.path.join(pasta, "finance.db")
            ):
                database.init_db()
                conn = database.get_db_connection()
                conn.execute("""
                    INSERT INTO cartoes
                        (nome, limite_total, fechamento_dia, vencimento_dia)
                    VALUES ('Cartão de teste', 1000, 10, 20);
                """)
                conn.execute("""
                    INSERT INTO lancamentos (
                        data, ano_mes, descricao, categoria, valor, metodo_pagamento
                    ) VALUES ('2026-10-05', '2026-10', 'Gasto de teste', 'Outros', 10, 'Pix');
                """)
                conn.execute("""
                    INSERT INTO gastos_recorrentes (descricao, valor_mensal, categoria)
                    VALUES ('Assinatura de teste', 20, 'Outros');
                """)
                conn.execute("""
                    UPDATE configuracoes
                    SET salario = 5000, outras_rendas = 500,
                        saldo_conta_corrente = 1234, valor_investido = 5678
                    WHERE id = 1;
                """)
                conn.commit()
                conn.close()

                resposta_sem_confirmacao = self.app.post(
                    "/configuracoes/excluir-dados",
                    data={"tipo": "todos"},
                )
                self.assertEqual(resposta_sem_confirmacao.status_code, 302)
                conn = database.get_db_connection()
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM lancamentos;").fetchone()[0], 1)
                conn.close()

                response = self.app.post(
                    "/configuracoes/excluir-dados",
                    data={"tipo": "todos", "confirmacao": "EXCLUIR TUDO"},
                )
                self.assertEqual(response.status_code, 302)

                conn = database.get_db_connection()
                for tabela in (
                    "lancamentos",
                    "parcelas_detalhe",
                    "compras_parceladas",
                    "recorrentes_status_mes",
                    "gastos_recorrentes",
                    "cartoes",
                ):
                    with self.subTest(tabela=tabela):
                        self.assertEqual(
                            conn.execute(f"SELECT COUNT(*) FROM {tabela};").fetchone()[0],
                            0,
                        )
                config = conn.execute("""
                    SELECT salario, outras_rendas, saldo_conta_corrente, valor_investido
                    FROM configuracoes WHERE id = 1;
                """).fetchone()
                self.assertEqual(tuple(config), (0, 0, 0, 0))
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM rendas_anuais;").fetchone()[0],
                    1,
                )
                self.assertEqual(
                    conn.execute(
                        "SELECT COUNT(*) FROM limites_categoria WHERE limite_mensal != 0;"
                    ).fetchone()[0],
                    0,
                )
                conn.close()

    def test_18_exclusao_por_semana_mes_e_ano_respeita_limites(self):
        with tempfile.TemporaryDirectory() as pasta:
            with patch.object(
                database, "DB_PATH", os.path.join(pasta, "finance.db")
            ):
                database.init_db()
                conn = database.get_db_connection()
                conn.executemany("""
                    INSERT INTO lancamentos (
                        data, ano_mes, descricao, categoria, valor, metodo_pagamento
                    ) VALUES (?, ?, ?, 'Outros', 10, 'Pix');
                """, [
                    ("2026-10-05", "2026-10", "Segunda"),
                    ("2026-10-11", "2026-10", "Domingo"),
                    ("2026-10-12", "2026-10", "Semana seguinte"),
                    ("2026-11-01", "2026-11", "Mês seguinte"),
                    ("2027-01-01", "2027-01", "Ano seguinte"),
                ])
                conn.commit()
                conn.close()

                response = self.app.post(
                    "/configuracoes/excluir-dados",
                    data={"tipo": "semana", "referencia": "2026-10-07"},
                )
                self.assertEqual(response.status_code, 302)
                conn = database.get_db_connection()
                restantes = {
                    row["descricao"] for row in conn.execute(
                        "SELECT descricao FROM lancamentos;"
                    ).fetchall()
                }
                conn.close()
                self.assertEqual(
                    restantes,
                    {"Semana seguinte", "Mês seguinte", "Ano seguinte"},
                )

                response = self.app.post(
                    "/configuracoes/excluir-dados",
                    data={"tipo": "mes", "referencia": "2026-11"},
                )
                self.assertEqual(response.status_code, 302)
                conn = database.get_db_connection()
                restantes = {
                    row["descricao"] for row in conn.execute(
                        "SELECT descricao FROM lancamentos;"
                    ).fetchall()
                }
                conn.close()
                self.assertEqual(restantes, {"Semana seguinte", "Ano seguinte"})

                response = self.app.post(
                    "/configuracoes/excluir-dados",
                    data={"tipo": "ano", "referencia": "2026"},
                )
                self.assertEqual(response.status_code, 302)
                conn = database.get_db_connection()
                restantes = {
                    row["descricao"] for row in conn.execute(
                        "SELECT descricao FROM lancamentos;"
                    ).fetchall()
                }
                conn.close()
                self.assertEqual(restantes, {"Ano seguinte"})


if __name__ == "__main__":
    unittest.main()
