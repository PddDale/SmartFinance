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


if __name__ == "__main__":
    unittest.main()
