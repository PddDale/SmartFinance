# SmartFinance

### Mais clareza para cuidar do seu dinheiro, no seu ritmo.

O SmartFinance é um aplicativo de finanças pessoais para acompanhar gastos, cartões, parcelas, despesas recorrentes e receitas em um só lugar. Os dados ficam guardados localmente no seu computador.

> **Privacidade:** O SmartFinance não envia seus dados financeiros a serviços de nuvem ou terceiros. A interface pode carregar alguns recursos visuais  externos, mas seus lançamentos não são enviados a esses serviços.

## Recursos

- Dashboard com resumo financeiro.
- Lançamentos de despesas, estornos e pagamentos avulsos.
- Destino de entradas na conta corrente ou em um cartão específico.
- Cartões com limite definido ou sem limite.
- Compras parceladas e gastos recorrentes.

## Veja o aplicativo

| Visão geral | Lançamentos |
| --- | --- |
| <img src="docs/images/smartfinance-dashboard.png" alt="Dashboard do SmartFinance" width="100%"><br><br>**Dashboard:** acompanhe patrimônio, saldo, investimentos, rendas, gastos e faturas em aberto. | <img src="docs/images/smartfinance-lancamentos.png" alt="Tela de lançamentos" width="100%"><br><br>**Lançamentos:** registre despesas, estornos e pagamentos avulsos, filtre por período e confirme pagamentos recorrentes. |

| Compras parceladas | Despesas recorrentes |
| --- | --- |
| <img src="docs/images/smartfinance-compras-parceladas.png" alt="Compras parceladas" width="100%"><br><br>**Compras parceladas:** veja o total contratado, as parcelas pagas e o saldo que ainda falta quitar. | <img src="docs/images/smartfinance-recorrentes.png" alt="Despesas recorrentes" width="100%"><br><br>**Recorrências:** organize assinaturas e contas fixas por mês e acompanhe os pagamentos ao longo do ano. |

| Cartões de crédito | Visão anual |
| --- | --- |
| <img src="docs/images/smartfinance-cartoes.png" alt="Cartões de crédito" width="100%"><br><br>**Cartões:** monitore limites, uso, faturas, datas de fechamento e vencimento. Também é possível cadastrar cartões sem limite. | <img src="docs/images/smartfinance-visao-anual.png" alt="Visão anual" width="100%"><br><br>**Visão anual:** compare rendas e despesas mês a mês e veja como os gastos se distribuem por categoria. |

## Instalação no Windows

Baixe a versão mais recente na [aba de releases do GitHub](https://github.com/PddDale/SmartFinance/releases).

Execute `SmartFinance-Setup.exe` e siga as instruções. O aplicativo abre no navegador e guarda os dados localmente.

O instalador oferece uma versão instalada e, quando disponível, uma versão portátil. Na versão portátil, mantenha a pasta inteira para preservar o aplicativo e os dados.

O executável já inclui o necessário para executar o aplicativo; não é preciso instalar Python para usar a versão para Windows.

####  Requisitos

- Windows
- Conexão com a internet para carregar alguns recursos visuais externos

## Uso

### Primeiros passos

1. Abra o SmartFinance pelo atalho ou pelo executável. A tela inicial mostra um resumo do mês selecionado.
2. Entre em **Configurações** e informe o ano de referência, salário, outras rendas, saldo da conta corrente e investimentos.
3. Ainda em **Configurações**, ajuste as categorias e os limites mensais que deseja acompanhar.
4. Cadastre seus cartões na aba **Cartões** antes de registrar compras feitas no crédito.

### Dashboard

Use o **Dashboard** para acompanhar:

- saldo da conta corrente, investimentos e patrimônio;
- renda, gastos e saldo líquido do mês;
- faturas de cartão e valores comprometidos;
- evolução dos gastos por categoria.

Use o seletor de mês para consultar períodos anteriores ou futuros.

### Lançamentos

Na aba **Lançamentos**, clique em **Novo lançamento** para registrar uma movimentação. Informe data, descrição, categoria, valor e método de pagamento.

- **Despesa:** registra um gasto normal e aparece com sinal `-`;
- **Estorno:** registra um valor devolvido e aparece com sinal `+`;
- **Pagamento avulso:** registra uma entrada que não faz parte de uma recorrência e aparece com sinal `+`.

Para estornos e pagamentos avulsos, escolha onde o valor deve ser considerado:

- **Conta Corrente** para refletir o valor na movimentação da conta;
- **Cartão de Crédito** para associar o valor a um cartão específico e à sua fatura.

Compras no cartão usam a data de fechamento e calculam automaticamente a fatura e o vencimento. Use os filtros de mês, categoria, método ou descrição para localizar registros. Cada lançamento pode ser editado ou excluído.

### Cartões

Na aba **Cartões**, clique em **Novo Cartão** e informe o nome, a bandeira, os dias de fechamento e vencimento e o limite. Marque **Cartão sem limite** quando o cartão não tiver um limite definido.

A tela mostra o limite utilizado, o valor disponível, a fatura aberta e os lançamentos de cada cartão. Alterar os dias de fechamento ou vencimento recalcula as datas das compras já registradas.

### Compras parceladas

Use **Compras Parceladas** para cadastrar uma compra com entrada e número de parcelas. O SmartFinance distribui os valores pelos meses e mostra:

- total da compra;
- quantidade e valor das parcelas;
- parcelas pagas;
- saldo ainda pendente.

Quando uma parcela for paga, registre o pagamento pela própria tela. Em compras feitas no cartão de crédito, isso apenas marca a parcela como quitada na fatura do mês e não cria uma nova compra no cartão. Para outros tipos de parcelamento, o lançamento correspondente é associado à parcela para evitar duplicidade.

### Despesas recorrentes

Na aba **Recorrentes**, cadastre assinaturas e contas fixas, como aluguel, internet ou serviços de streaming. Defina o valor, a categoria, o dia de cobrança e o método de pagamento.

É possível ativar ou pausar uma cobrança em meses específicos. Quando uma cobrança vencer, confirme o pagamento na área de lançamentos; o SmartFinance registra o lançamento e marca aquele mês como pago.

### Visão anual

Use a aba **Visão Anual** para comparar os meses do ano, visualizar rendas e despesas e identificar as categorias que mais influenciaram o resultado.

### Importação e backup

Na aba **Lançamentos**, use **Importar Excel** para carregar uma planilha. Relacione as colunas de data, descrição e valor, escolha uma categoria padrão e revise a prévia antes de importar.

Na aba **Configurações**, use **Criar backup local** para baixar uma cópia dos dados. O arquivo segue o padrão `BackupSmartFin - DDMMAAAA.json` e pode ser importado novamente pela mesma tela.

O backup local é um arquivo JSON. Ao importar uma cópia, o SmartFinance mostra uma prévia, evita duplicidades e permite revisar conflitos antes de confirmar a mesclagem. Faça um backup antes de importar outro arquivo.

Ao instalar ou atualizar o aplicativo e escolher uma pasta que contenha um backup `BackupSmartFin - DDMMAAAA.json` (ou um dos nomes legados reconhecidos), o SmartFinance converte automaticamente esse arquivo para o banco local. O JSON só é excluído depois que a conversão termina com sucesso; se houver qualquer erro, ele é preservado para que possa ser importado manualmente.

O aplicativo começa sem dados financeiros. Na categoria **Dados e backup**, use **Selecionar caminho** para escolher uma pasta: se ela já contiver `finance.db`, esse banco poderá ser usado; caso contrário, um banco vazio será criado.

Ao atualizar uma instalação existente, o instalador preserva automaticamente o último local de armazenamento do banco escolhido pelo usuário. A etapa de migração só é exibida em uma instalação nova.

> Dica: faça um backup antes de excluir dados, atualizar o aplicativo ou importar uma planilha grande.

## Como funciona

O aplicativo é executado localmente e abre sua interface no navegador. O banco de dados fica no computador, sem conexão bancária automática. Faça backups periódicos e não compartilhe arquivos que contenham informações financeiras.

Em uma execução manual, é possível definir a variável de ambiente `SMARTFINANCE_SECRET_KEY` para fornecer a chave usada pelas sessões da interface. Se ela não for definida, o aplicativo gera uma chave aleatória ao iniciar.

Enquanto uma aba do SmartFinance estiver aberta,  ela envia um sinal periódico ao aplicativo. Se todas as abas forem fechadas, o programa encerra automaticamente após 30 segundos.

## Estrutura

```text
SmartFinance/
├── Recursos/Codigo/          # Aplicação
├── Recursos/Interface/       # Telas e estilos
├── Recursos/Testes/          # Testes automatizados
└── Recursos/Dados/           # Dados locais
```

Sugestões e problemas podem ser registrados na página de [issues do GitHub](https://github.com/PddDale/SmartFinance/issues).
