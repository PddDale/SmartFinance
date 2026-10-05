# 🪙 SmartFinance - Sistema de Controle Financeiro Pessoal

Aplicação web profissional desenvolvida em **Python (Flask)** com servidor de produção **Waitress (WSGI)**, persistência em banco relacional leve **SQLite**, interface visual em **Design Monocromático de Alto Contraste (Preto, Branco e Cinza)** com **Aceleração por GPU**, componentes visuais responsivos (**Bootstrap 5.3**) e gráficos analíticos (**Chart.js**).

---

## 🎨 Identidade Visual e Filosofia de Design

- **Base Monocromática (Preto, Branco e Cinza):** Todo o corpo da aplicação, cabeçalhos, painéis e tabelas utilizam tons puros de preto, branco e cinza para uma interface limpa, sóbria e focada.
- **Botões de Ação com Cores Vivas (Alto Contraste):** Apenas os botões de ação interativos possuem cores primárias sólidas (Azul para criação, Verde para salvar/superávit, Vermelho para exclusão/saída e Âmbar para ajustes), criando um contraste visual instantâneo e intuitivo.
- **Aceleração por GPU & Alta Performance:**
  - Eliminação de filtros Gaussianos pesados em favor de renderização direta com camadas aceleradas por hardware (`transform: translateZ(0)` e `backface-visibility: hidden`).
  - Animações leves e rápidas no Chart.js para eliminar travamentos e quedas de quadros no Windows.
- **Design dos Cartões de Crédito Preservado:** Visual dos cartões de crédito físicos/virtuais mantido com chip dourado, bandeiras e monitoramento de faturas.
- **Opções de Encerramento (Salvar e Sair / Sair sem Salvar):** Botão dedicado no cabeçalho permitindo ao usuário escolher entre:
  1. **Salvar e Sair:** Sincroniza e confirma todas as alterações pendentes no banco SQLite local antes de desligar o servidor e fechar a aba.
  2. **Sair sem Salvar:** Encerra o servidor imediatamente sem gravar novas alterações pendentes.

---

## ⚡ Servidor de Produção WSGI (Waitress)

A aplicação agora utiliza o servidor **Waitress**, um servidor WSGI pronto para produção em ambiente Windows que:
- **Remove completamente o aviso:** `WARNING: This is a development server. Do not use it in a production deployment.`
- Executa requisições de forma multithread (múltiplas threads simultâneas), eliminando gargalos de requisições travadas e melhorando significativamente o tempo de resposta e carregamento de assets.

---

## 🚀 Principais Funcionalidades

1. **Dashboard com KPIs:** Patrimônio Total, Saldo em Conta Corrente, Investimentos, Gastos do Mês e Faturas em Aberto.
2. **Lançamentos Avulsos:** Controle de gastos diários com categorização e filtros por texto, mês, categoria e método de pagamento.
3. **Múltiplos Cartões de Crédito:** Controle de datas de fechamento e vencimento com cálculo automático da alocação de compras na fatura correta.
4. **Compras Parceladas:** Projeção cronológica das parcelas no banco de dados e cronograma visual com sanfona de detalhes.
5. **Gastos Recorrentes:** Controle de contas fixas e assinaturas com chave de ativação/pausa mensal instantânea via AJAX.
6. **Visão Anual:** Tabela comparativa dos 12 meses idêntica à do Excel e gráficos de evolução.
7. **Exportação e Backup:** Download em um clique do arquivo `database.json`.

---

## 🛠️ Como Executar

### Opção 1: Inicialização em 1 Clique (Recomendado)
Dê um duplo clique no arquivo **`run.bat`**:
```cmd
run.bat
```
O script iniciará o servidor Waitress e abrirá seu navegador automaticamente em `http://127.0.0.1:5000`.

### Opção 2: Linha de Comando (PowerShell / CMD)
```powershell
py -m pip install -r requirements.txt
py app.py
```
Acesse: **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

---

## 🛑 Como Encerrar o Aplicativo

Clique no botão vermelho **Sair** no canto superior direito da barra de navegação:
- Selecione **"Salvar e Sair"** para persistir os dados no banco SQLite e desligar o servidor.
- Selecione **"Sair sem Salvar"** para finalizar o servidor sem persistir novas alterações.

---

## 🔮 Funcionalidades Futuras (Roadmap)

As funcionalidades abaixo estão planejadas para versões futuras do SmartFinance:

| # | Funcionalidade | Descrição |
|---|---|---|
| 1 | 🤖 **Auto-categorização com IA** | Classificação automática de lançamentos usando modelos de Inteligência Artificial (locais via Ollama/LM Studio ou na nuvem via OpenAI/Gemini), eliminando a necessidade de categorização manual. |
| 2 | 🌙 **Dark Mode** | Tema escuro alternativo para reduzir a fadiga visual em ambientes com pouca luz, com alternância instantânea e persistência da preferência do usuário. |
| 3 | 🌐 **Outros Idiomas (i18n)** | Suporte a internacionalização (Inglês, Espanhol e outros), permitindo que usuários de diferentes países utilizem o sistema em sua língua nativa. |
| 4 | 🏦 **Contas Globais** | Gerenciamento de múltiplas contas bancárias (corrente, poupança, carteiras digitais), com visão consolidada do saldo e transferências entre contas. |
| 5 | 📈 **Plataforma de Monitoramento de Investimentos** | Painel dedicado para acompanhamento de renda fixa, renda variável, FIIs e criptoativos, com cotações em tempo real, rentabilidade acumulada e comparativo com benchmarks (CDI, IBOV, IPCA). |
