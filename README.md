# SmartFinance

### Mais clareza para cuidar do seu dinheiro, no seu ritmo.

O SmartFinance é um aplicativo web de finanças pessoais para acompanhar gastos, cartões, parcelas e despesas recorrentes em um só lugar. Veja um resumo da sua vida financeira, registre movimentações e consulte seus gastos ao longo do ano — com os dados guardados localmente no seu computador.

> **Privacidade:** O SmartFinance não se conecta a bancos nem envia seus dados financeiros a serviços de nuvem. A interface carrega alguns recursos visuais por CDNs externos, mas não envia seus lançamentos a esses serviços.

## O que você pode fazer hoje

- **Entender o panorama financeiro:** consulte indicadores de patrimônio, saldo, investimentos, gastos do mês e faturas em aberto.
- **Acompanhar gastos do dia a dia:** registre lançamentos, receba sugestões de descrições já usadas, organize-os por categoria e filtre por período, método de pagamento ou texto.
- **Personalizar a exibição:** escolha o formato das datas e informe valores com vírgula decimal nos campos de rendas e saldos.
- **Controlar cartões:** cadastre cartões e acompanhe compras e faturas conforme as datas de fechamento e vencimento.
- **Planejar parcelas:** registre compras parceladas, consulte a projeção e edite os dados da compra. Se já houver pagamentos confirmados, os valores e o cronograma ficam protegidos; é possível editar descrição, categoria e observação sem perder os lançamentos pagos.
- **Lembrar despesas recorrentes:** informe desde quando a conta é cobrada, organize o ano inteiro, pause meses específicos e confirme os pagamentos vencidos agrupados por conta na aba de lançamentos.
- **Registrar pagamentos mensais:** marque parcelas e recorrências como pagas e gere o lançamento com o método de pagamento informado.
- **Observar a evolução ao longo do ano:** compare os meses em uma visão anual com tabelas e gráficos.
- **Importar compras do Excel:** use o assistente para relacionar as colunas de data, descrição e preço e, opcionalmente, a categoria de cada linha. Cabeçalhos reconhecidos são mapeados automaticamente e uma mesma coluna não pode ser usada em mais de um campo. Escolha a detecção automática ou o padrão decimal brasileiro (`1.234,56`) ou internacional (`1,234.56`). Categorias da planilha precisam corresponder às categorias cadastradas; emojis e símbolos decorativos são ignorados nessa comparação. Sem coluna de categoria, é aplicada uma categoria padrão.
- **Planejar rendas variáveis:** opcionalmente informe salário e outras rendas mês a mês; por padrão, a renda mensal é uniforme.
- **Guardar uma cópia dos dados:** exporte um backup em JSON.

## O que vem pela frente

Estas são ideias para versões futuras; ainda não estão disponíveis no aplicativo. A ordem e o escopo podem mudar conforme o projeto evolui.

- [ ] **Open Finance:** estudar uma integração de leitura de transações com um provedor adequado, incluindo custos, consentimento, segurança e armazenamento dos tokens. A proposta é mostrar uma prévia para revisão antes de importar e permitir revogar a conexão.
- [ ] **Importar extratos CSV e OFX:** carregar arquivos exportados pelo banco, revisar as transações e identificar possíveis duplicatas antes de gravar.
- [ ] **Contas bancárias:** organizar várias contas e visualizar saldos consolidados.
- [ ] **Categorizar lançamentos com assistência:** sugerir categorias a partir das descrições, mantendo a possibilidade de revisar e corrigir as sugestões.
- [ ] **Tema escuro:** oferecer uma alternativa de aparência com preferência salva.
- [ ] **Mais idiomas:** ampliar o acesso com traduções para outros idiomas.
- [ ] **Acompanhar investimentos:** explorar uma área para organizar investimentos e acompanhar sua evolução.

O SmartFinance ainda **não oferece conexão bancária automática**. A importação de planilhas Excel cria lançamentos locais após o mapeamento e a validação das colunas. A ideia para Open Finance é consultar transações somente após autorização da pessoa usuária — não realizar pagamentos. Uma integração desse tipo exigirá escolher um provedor e explicar com clareza quais dados são compartilhados e como são protegidos.

## Como funciona

O aplicativo é executado no seu computador e aberto pelo navegador. Ele usa Python e Flask na aplicação, SQLite para guardar os dados localmente e Waitress como servidor web. A interface usa HTML, CSS e JavaScript.

O arquivo do banco de dados fica em `Recursos/Dados/finance.db`. Faça backups regularmente e não compartilhe esse arquivo: ele pode conter informações financeiras pessoais. A exportação JSON está disponível em **Configurações**.

### Requisitos

- Windows
- Python disponível pelo comando `py`
- Conexão com a internet na primeira execução para instalar dependências e carregar recursos visuais externos

### Política de dependências Python

O SmartFinance não usa nem deve criar uma pasta `.venv` ou outro ambiente virtual dentro do projeto. O inicializador e as instruções de instalação usam o Python selecionado pelo comando `py` e instalam os pacotes listados em `Recursos\Dependencias\requirements.txt` no local padrão desse Python, para que outros projetos que usem a mesma instalação também possam aproveitar os pacotes.

Ao atualizar o projeto, mantenha esse comportamento: não direcione a instalação para uma pasta local do repositório nem adicione a criação automática de um ambiente virtual. Como a instalação é compartilhada, atualizar pacotes pode afetar outros projetos que usem essa mesma instalação do Python; em alguns computadores, também pode ser necessário ter permissão para instalar pacotes.

### Início rápido

Na raiz do projeto, dê um duplo clique em `SmartFinance.bat`. O script prepara as dependências e abre o aplicativo no navegador em `http://127.0.0.1:5000`.

### Iniciar pelo terminal

No PowerShell ou Prompt de Comando, a partir da raiz do projeto:

```powershell
py -m pip install --upgrade -r Recursos\Dependencias\requirements.txt
py Recursos\Codigo\app.py
```

Depois, abra [http://127.0.0.1:5000](http://127.0.0.1:5000) no navegador.

### Encerrar

Use o botão **Sair** na barra superior e escolha uma das opções apresentadas:

- **Salvar e Sair** para salvar os dados e encerrar o aplicativo.
- **Sair sem Salvar** para encerrar sem persistir as alterações pendentes.

## Executar os testes

Na raiz do projeto, execute:

```powershell
py -m unittest discover -s Recursos\Testes -t . -p test_app.py
```

## Estrutura do projeto

```text
SmartFinance/
├── SmartFinance.bat
├── README.md
├── Recursos/
│   ├── Codigo/          # Aplicação Flask, modelos e acesso ao banco
│   ├── Interface/       # Templates, CSS e JavaScript
│   ├── Dependencias/    # Dependências Python
│   ├── Testes/          # Testes automatizados
│   └── Dados/           # Banco SQLite local
└── .gitignore
```

## Ideias, problemas e contribuições

Encontrou um problema ou tem uma sugestão? Abra uma issue neste repositório descrevendo o que aconteceu ou como a ideia ajudaria. Contribuições são bem-vindas; para mudanças maiores, uma issue antes do pull request ajuda a alinhar a solução.

Ao reportar um problema, não anexe extratos, credenciais, backups ou outros dados financeiros reais. Se precisar demonstrar um caso, use informações fictícias.
