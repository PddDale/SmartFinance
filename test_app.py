import unittest
from unittest.mock import patch
import json
from app import app
import database

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

        res = self.app.post("/api/calcular-fatura", 
            data=json.dumps({"data": "2026-10-26", "cartao_id": cartao["id"]}),
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data["success"])
        self.assertIn("fatura_mes", data)
        self.assertIn("data_vencimento", data)

    def test_09_exportar_json(self):
        response = self.app.get("/configuracoes/exportar-json")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn("configuracoes", data)
        self.assertIn("saldos", data)
        self.assertIn("cartoes", data)
        self.assertIn("lancamentos", data)

    def test_10_novo_lancamento_and_delete(self):
        # Inserir novo lançamento
        res = self.app.post("/lancamentos/novo", data={
            "data": "2026-10-05",
            "descricao": "Teste Automatizado Lanche",
            "categoria": "Alimentação",
            "valor": "35,50",
            "metodo_pagamento": "Pix",
            "observacao": "Teste unitário"
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Teste Automatizado Lanche", res.data)

        # Buscar id para excluir
        conn = database.get_db_connection()
        row = conn.execute("SELECT id FROM lancamentos WHERE descricao = 'Teste Automatizado Lanche';").fetchone()
        conn.close()
        self.assertIsNotNone(row)

        res_del = self.app.post(f"/lancamentos/excluir/{row['id']}", follow_redirects=True)
        self.assertEqual(res_del.status_code, 200)

    @patch("os._exit")
    def test_11_api_encerrar(self, mock_exit):
        res = self.app.post("/api/encerrar")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data["success"])
        self.assertIn("SmartFinance", data["message"])

    def test_12_api_categorizar_regras(self):
        """Testa auto-categorização por regras inteligentes."""
        casos = [
            ("iFood almoço executivo", "Alimentação"),
            ("Uber corrida aeroporto", "Transporte"),
            ("Netflix assinatura mensal", "Lazer"),
            ("Drogasil remédio pressão", "Saúde"),
            ("Conta de luz CEMIG", "Moradia"),
        ]
        for descricao, categoria_esperada in casos:
            with self.subTest(descricao=descricao):
                res = self.app.post("/api/categorizar",
                    data=json.dumps({"descricao": descricao}),
                    content_type="application/json"
                )
                self.assertEqual(res.status_code, 200)
                data = json.loads(res.data)
                self.assertTrue(data["success"])
                self.assertEqual(data["categoria"], categoria_esperada,
                    f"Falhou para '{descricao}': esperado '{categoria_esperada}', obteve '{data['categoria']}'")

    def test_13_api_categorizar_historico(self):
        """Testa auto-categorização por histórico do usuário."""
        # Inserir lançamento para treinar o histórico
        self.app.post("/lancamentos/novo", data={
            "data": "2026-10-01",
            "descricao": "Mercadinho do Zé",
            "categoria": "Alimentação",
            "valor": "50.00",
            "metodo_pagamento": "Pix"
        })
        res = self.app.post("/api/categorizar",
            data=json.dumps({"descricao": "Mercadinho do Zé"}),
            content_type="application/json"
        )
        data = json.loads(res.data)
        self.assertTrue(data["success"])
        # Pode vir do histórico ou das regras, mas deve ser Alimentação
        self.assertEqual(data["categoria"], "Alimentação")
        # Limpar lançamento de teste
        conn = database.get_db_connection()
        conn.execute("DELETE FROM lancamentos WHERE descricao='Mercadinho do Zé';")
        conn.commit()
        conn.close()

if __name__ == "__main__":
    unittest.main()
