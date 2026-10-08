// JavaScript Interativo para o Controle Financeiro Pessoal

document.addEventListener("DOMContentLoaded", function () {
    // 1. Inicializar Tooltips do Bootstrap
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // 2. Fechar alertas automaticamente após 5 segundos
    setTimeout(function () {
        const alerts = document.querySelectorAll('.alert-dismissible');
        alerts.forEach(function (alert) {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            bsAlert.close();
        });
    }, 5000);

    setupLocalDateInputs();

    // 3. Monitoramento dinâmico de Método de Pagamento e Cartão (Formulário de Lançamento)
    setupMetodoPagamentoListener("metodo_pagamento", "cartao_container", "cartao_id", "data_lancamento", "fatura_preview");
    setupMetodoPagamentoListener("modal_metodo_pagamento", "modal_cartao_container", "modal_cartao_id", "modal_data_lancamento", "modal_fatura_preview");
    setupMetodoPagamentoListener("edit_metodo_pagamento", "edit_cartao_container", "edit_cartao_id", "edit_data", null);

    // 4. Cálculo dinâmico de parcelas no modal de Compra Parcelada
    setupCalculoParcelas();
    setupMetodoPagamentoListener(
        "edit_parc_metodo", "edit_parc_cartao_container",
        "edit_parc_cartao", "edit_parc_data", null
    );
    setupEditarCompraParcelada();

    // 5. Configurar listener de alternância de status de recorrentes (AJAX)
    setupRecorrentesToggle();

    // 6. Configurar botão de Sair e Salvar
    setupSairAplicacao();

    // 7. Auto-categorização de despesas por IA de regras
    setupAutoCategorizar();

    // 8. Sincronizar os campos de renda mensal e anual
    setupRendasAnoMes();

    // 9. Presets de cores de cartões com opção de cor personalizada
    setupCoresCartoes();

    // 10. Rendas variáveis por mês
    setupRendaVariavelMensal();

    // 11. Pagamento rápido de parcelas e recorrências
    setupModalPagamento();

    // 12. Importação guiada de planilhas Excel
    setupExcelImportWizard();

    // 13. Exibição do mês da fatura conforme a preferência de data
    setupFormattedMonthSelector();

    // 14. Sugestões de descrições de lançamentos anteriores
    setupLancamentoAutocomplete();

    // 15. Contraste das barras de limite nos cartões
    setupCreditCardProgressContrast();
});

function formatarDataLocal(dataIso) {
    const partes = String(dataIso || "").match(/^(\d{4})-(\d{2})-(\d{2})$/);
    return partes ? `${partes[3]}/${partes[2]}/${partes[1]}` : "";
}

function setupLocalDateInputs() {
    document.querySelectorAll("[data-local-date-input]").forEach(function (grupo) {
        const campoIso = grupo.querySelector("[data-date-value]");
        const campoExibicao = grupo.querySelector("[data-date-display]");
        const botaoCalendario = grupo.querySelector("[data-date-picker-button]");
        if (!campoIso || !campoExibicao || !botaoCalendario) return;

        function sincronizarExibicao() {
            campoExibicao.value = formatarDataLocal(campoIso.value);
            campoExibicao.setCustomValidity("");
        }

        function sincronizarValor() {
            const partes = campoExibicao.value.trim().match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
            if (!partes) {
                campoIso.value = "";
                campoExibicao.setCustomValidity(
                    campoExibicao.value ? "Informe a data no formato DD/MM/AAAA." : ""
                );
                return;
            }

            const [, dia, mes, ano] = partes;
            const dataIso = `${ano}-${mes}-${dia}`;
            const data = new Date(`${dataIso}T00:00:00`);
            const valida = Number.isFinite(data.getTime()) &&
                data.getFullYear() === Number(ano) &&
                data.getMonth() === Number(mes) - 1 &&
                data.getDate() === Number(dia);
            if (!valida) {
                campoIso.value = "";
                campoExibicao.setCustomValidity("Informe uma data válida no formato DD/MM/AAAA.");
                return;
            }

            campoIso.value = dataIso;
            campoExibicao.setCustomValidity("");
            campoIso.dispatchEvent(new Event("change", { bubbles: true }));
        }

        campoExibicao.addEventListener("input", sincronizarValor);
        campoIso.addEventListener("change", sincronizarExibicao);
        botaoCalendario.addEventListener("click", function () {
            if (typeof campoIso.showPicker === "function") {
                campoIso.showPicker();
            } else {
                campoIso.click();
            }
        });
        sincronizarExibicao();
    });
}

function setupCreditCardProgressContrast() {
    document.querySelectorAll(".credit-card-ui").forEach(function (cartao) {
        const barra = cartao.querySelector("[data-contrast-progress]");
        if (!barra) return;

        const cor = getComputedStyle(cartao).backgroundColor;
        const componentes = cor.match(/[\d.]+/g);
        if (!componentes || componentes.length < 3) return;

        const rgb = componentes.slice(0, 3).map(Number);
        const luminancia = rgb
            .map(function (valor) {
                const canal = valor / 255;
                return canal <= 0.04045
                    ? canal / 12.92
                    : Math.pow((canal + 0.055) / 1.055, 2.4);
            })
            .reduce(function (soma, canal, indice) {
                return soma + canal * [0.2126, 0.7152, 0.0722][indice];
            }, 0);

        const contrastePreto = (luminancia + 0.05) / 0.05;
        const contrasteBranco = 1.05 / (luminancia + 0.05);
        const preenchimento = contrasteBranco > contrastePreto
            ? "255, 255, 255"
            : "0, 0, 0";

        barra.style.setProperty("--progress-fill-color", `rgb(${preenchimento})`);
        barra.style.setProperty(
            "--progress-track-color",
            `rgba(${preenchimento}, 0.28)`
        );
    });
}

function parseValorLocalizado(valor) {
    let texto = String(valor || "").trim().replace(/R\$/g, "").replace(/\s/g, "");
    if (!texto) return NaN;
    if (texto.includes(",") && texto.includes(".")) {
        texto = texto.lastIndexOf(",") > texto.lastIndexOf(".")
            ? texto.replace(/\./g, "").replace(",", ".")
            : texto.replace(/,/g, "");
    } else if (texto.includes(",")) {
        texto = texto.replace(/\./g, "").replace(",", ".");
    } else if (/^-?\d{1,3}(?:\.\d{3})+$/.test(texto)) {
        texto = texto.replace(/\./g, "");
    }
    return Number(texto);
}

function formatarMesAno(mes, ano) {
    const formato = document.body.dataset.formatoData || "dd/mm/aaaa";
    if (formato === "dd/mm/aaaa") return `${mes}/${ano}`;
    const data = new Date(0);
    data.setFullYear(Number(ano), Number(mes) - 1, 1);
    return new Intl.DateTimeFormat("pt-BR", {
        month: "long",
        year: "numeric"
    }).format(data);
}

function setupFormattedMonthSelector() {
    document.querySelectorAll("[data-formatted-month-selector]").forEach(function (seletor) {
        const form = seletor.closest("form");
        const mes = seletor.querySelector("[data-month-selector-month]");
        const ano = seletor.querySelector("[data-month-selector-year]");
        const valorMes = seletor.querySelector("[data-month-selector-value]");
        if (!form || !mes || !ano || !valorMes) return;

        function atualizarOpcoes() {
            Array.from(mes.options).forEach(function (opcao) {
                if (opcao.value) {
                    opcao.textContent = formatarMesAno(opcao.value, ano.value);
                }
            });
        }

        function atualizarValorEEnviar() {
            if (!ano.reportValidity()) return;
            valorMes.value = mes.value
                ? `${String(ano.value).padStart(4, "0")}-${mes.value}`
                : "";
            if (seletor.dataset.submitOnChange === "true") {
                form.requestSubmit();
            }
        }

        ano.addEventListener("input", function () {
            atualizarOpcoes();
            valorMes.value = mes.value
                ? `${String(ano.value).padStart(4, "0")}-${mes.value}`
                : "";
        });
        ano.addEventListener("change", atualizarValorEEnviar);
        mes.addEventListener("change", atualizarValorEEnviar);
    });
}

function setupLancamentoAutocomplete() {
    document.querySelectorAll("[data-lancamento-autocomplete]").forEach(function (input) {
        const lista = document.createElement("div");
        lista.className = "launch-suggestions d-none";
        lista.id = `${input.id}_sugestoes`;
        lista.setAttribute("role", "listbox");
        input.setAttribute("aria-autocomplete", "list");
        input.setAttribute("aria-controls", lista.id);
        input.setAttribute("aria-expanded", "false");
        input.parentElement.appendChild(lista);

        let sugestoes = [];
        let indiceAtivo = -1;
        let requisicaoAtual = 0;
        let ignorarProximaBusca = false;

        function fecharLista() {
            lista.classList.add("d-none");
            input.setAttribute("aria-expanded", "false");
            input.removeAttribute("aria-activedescendant");
            indiceAtivo = -1;
        }

        function selecionar(sugestao) {
            input.value = sugestao;
            fecharLista();
            ignorarProximaBusca = true;
            input.dispatchEvent(new Event("input", { bubbles: true }));
        }

        function mostrarErro() {
            sugestoes = [];
            lista.replaceChildren();
            const aviso = document.createElement("div");
            aviso.className = "launch-suggestions-message";
            aviso.setAttribute("role", "status");
            aviso.textContent = "Não foi possível carregar as sugestões.";
            lista.appendChild(aviso);
            lista.classList.remove("d-none");
            input.setAttribute("aria-expanded", "true");
        }

        function mostrarSugestoes(valores) {
            sugestoes = valores;
            indiceAtivo = -1;
            lista.replaceChildren();
            if (!sugestoes.length) {
                fecharLista();
                return;
            }

            sugestoes.forEach(function (sugestao, indice) {
                const opcao = document.createElement("button");
                opcao.type = "button";
                opcao.className = "launch-suggestion";
                opcao.id = `${lista.id}_opcao_${indice}`;
                opcao.setAttribute("role", "option");
                opcao.setAttribute("aria-selected", "false");
                opcao.textContent = sugestao;
                opcao.addEventListener("mousedown", function (evento) {
                    evento.preventDefault();
                    selecionar(sugestao);
                });
                lista.appendChild(opcao);
            });
            lista.classList.remove("d-none");
            input.setAttribute("aria-expanded", "true");
        }

        input.addEventListener("input", function () {
            if (ignorarProximaBusca) {
                ignorarProximaBusca = false;
                return;
            }
            const termo = this.value.trim();
            const requisicao = ++requisicaoAtual;
            if (!termo) {
                sugestoes = [];
                fecharLista();
                return;
            }
            sugestoes = [];
            fecharLista();

            fetch(`/api/lancamentos/sugestoes?q=${encodeURIComponent(termo)}`)
                .then(function (resposta) {
                    if (!resposta.ok) throw new Error("Falha ao buscar descrições anteriores.");
                    return resposta.json();
                })
                .then(function (dados) {
                    if (requisicao !== requisicaoAtual || input.value.trim() !== termo) return;
                    if (!Array.isArray(dados.sugestoes)) {
                        throw new Error("Resposta inválida ao buscar descrições anteriores.");
                    }
                    mostrarSugestoes(dados.sugestoes);
                })
                .catch(function (erro) {
                    if (requisicao !== requisicaoAtual) return;
                    console.error("Erro ao carregar sugestões de lançamentos:", erro);
                    mostrarErro();
                });
        });

        input.addEventListener("keydown", function (evento) {
            if (lista.classList.contains("d-none") || !sugestoes.length) {
                if (evento.key === "Escape") fecharLista();
                return;
            }
            if (evento.key === "ArrowDown" || evento.key === "ArrowUp") {
                evento.preventDefault();
                const passo = evento.key === "ArrowDown" ? 1 : -1;
                indiceAtivo = (indiceAtivo + passo + sugestoes.length) % sugestoes.length;
                Array.from(lista.children).forEach(function (opcao, indice) {
                    const ativo = indice === indiceAtivo;
                    opcao.classList.toggle("active", ativo);
                    opcao.setAttribute("aria-selected", String(ativo));
                });
                input.setAttribute("aria-activedescendant", `${lista.id}_opcao_${indiceAtivo}`);
            } else if (evento.key === "Enter" && indiceAtivo >= 0) {
                evento.preventDefault();
                selecionar(sugestoes[indiceAtivo]);
            } else if (evento.key === "Escape") {
                fecharLista();
            }
        });

        input.addEventListener("blur", function () {
            window.setTimeout(fecharLista, 120);
        });
    });
}

function setupRendasAnoMes() {
    const modoInput = document.getElementById("modo_renda");
    document.querySelectorAll("[data-income-key]").forEach(function (input) {
        input.addEventListener("input", function () {
            const anual = this.name.endsWith("_anual") || this.name.endsWith("_anuais");
            const correspondente = Array.from(document.querySelectorAll("[data-income-key]"))
                .find(function (campo) {
                    return campo !== input &&
                        campo.dataset.incomeKey === input.dataset.incomeKey &&
                        campo.name.endsWith(anual ? "_mensal" : (input.dataset.incomeKey === "salario" ? "_anual" : "_anuais"));
                });
            if (!correspondente) return;

            const valor = parseValorLocalizado(this.value);
            correspondente.value = this.value === "" || !Number.isFinite(valor)
                ? ""
                : (anual ? valor / 12 : valor * 12).toLocaleString("pt-BR", {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2
                });
            if (modoInput) modoInput.value = anual ? "anual" : "mensal";
        });
    });

    document.querySelectorAll("[data-min]").forEach(function (input) {
        function validarMinimo() {
            const valor = parseValorLocalizado(input.value);
            const minimo = Number(input.dataset.min);
            input.setCustomValidity(
                input.value.trim() && Number.isFinite(valor) && valor < minimo
                    ? `Informe um valor igual ou superior a ${minimo}.`
                    : ""
            );
        }
        input.addEventListener("input", validarMinimo);
        input.addEventListener("change", validarMinimo);
    });
}

function setupCoresCartoes() {
    document.querySelectorAll("[data-color-preset]").forEach(function (select) {
        const colorInput = document.getElementById(select.dataset.colorPreset);
        if (!colorInput) return;
        select.addEventListener("change", function () {
            if (this.value) colorInput.value = this.value;
        });
        colorInput.addEventListener("input", function () {
            select.value = "";
        });
    });
}

function setupRendaVariavelMensal() {
    const toggle = document.getElementById("renda_variavel_mensal");
    const campos = document.getElementById("rendas_mensais_container");
    if (!toggle || !campos) return;
    toggle.addEventListener("change", function () {
        campos.classList.toggle("d-none", !this.checked);
    });
}

function setupModalPagamento() {
    const form = document.getElementById("formRegistrarPagamento");
    const metodo = document.getElementById("metodo_pagamento_pago");
    const containerCartao = document.getElementById("cartao_pagamento_container");
    const cartao = document.getElementById("cartao_pagamento_id");
    if (!form || !metodo || !containerCartao || !cartao) return;

    function atualizarCartao() {
        const usaCartao = metodo.value === "Cartão de Crédito";
        containerCartao.classList.toggle("d-none", !usaCartao);
        cartao.required = usaCartao;
    }
    metodo.addEventListener("change", atualizarCartao);

    window.abrirModalPagamento = function (botao) {
        form.action = botao.dataset.paymentUrl;
        document.getElementById("descricaoModalPagamento").textContent =
            `${botao.dataset.paymentDescription}. O lançamento será criado após sua confirmação.`;
        document.getElementById("tituloModalPagamento").textContent =
            botao.dataset.paymentMonth ? "Registrar pagamento recorrente" : "Registrar pagamento da parcela";
        document.getElementById("mesPagamento").value = botao.dataset.paymentMonth || "";
        metodo.value = botao.dataset.paymentMethod || "Pix";
        cartao.value = botao.dataset.paymentCard || "";
        atualizarCartao();
        bootstrap.Modal.getOrCreateInstance(
            document.getElementById("modalRegistrarPagamento")
        ).show();
    };
    atualizarCartao();
}

function setupExcelImportWizard() {
    const arquivoInput = document.getElementById("excelImportFile");
    const botaoPrevia = document.getElementById("excelPreviewButton");
    const botaoImportar = document.getElementById("excelImportButton");
    const mapeamento = document.getElementById("excelImportMapping");
    const status = document.getElementById("excelImportStatus");
    const metodo = document.getElementById("excel_metodo");
    const cartaoContainer = document.getElementById("excel_cartao_container");
    const cartao = document.getElementById("excel_cartao_id");
    if (!arquivoInput || !botaoPrevia || !botaoImportar || !mapeamento || !status) return;

    let arquivoAtual = null;
    function normalizarCabecalhoExcel(texto) {
        return String(texto || "")
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .toLowerCase()
            .replace(/[^a-z0-9]/g, "");
    }

    function mapearColunasConhecidas(colunas) {
        const seletores = Array.from(
            document.querySelectorAll(".excel-column-map")
        );
        const sinonimos = {
            data: ["data", "date", "datadacompra"],
            descricao: ["descricao", "description", "compra", "nomedacompra"],
            valor: ["valor", "preco", "price", "valorr", "amount"],
            categoria: ["categoria", "category", "tipodecategoria"]
        };

        seletores.forEach(function (select) {
            const campo = select.id.replace(/^excel_|_col$/g, "");
            const correspondencia = colunas.find(function (coluna) {
                return sinonimos[campo].includes(
                    normalizarCabecalhoExcel(coluna.nome)
                );
            });
            if (correspondencia) {
                select.value = String(correspondencia.indice);
            }
        });

        atualizarDisponibilidadeColunas();
        seletores.forEach(function (select) {
            select.addEventListener("change", function () {
                atualizarDisponibilidadeColunas(select);
            });
        });
    }

    function atualizarDisponibilidadeColunas(preferido) {
        const seletores = Array.from(
            document.querySelectorAll(".excel-column-map")
        );
        if (preferido && preferido.value) {
            seletores.forEach(function (select) {
                if (select !== preferido && select.value === preferido.value) {
                    select.value = "";
                }
            });
        }

        const selecionados = seletores
            .filter(select => select.value)
            .map(select => select.value);
        seletores.forEach(function (select) {
            Array.from(select.options).forEach(function (opcao) {
                opcao.disabled = Boolean(
                    opcao.value &&
                    opcao.value !== select.value &&
                    selecionados.includes(opcao.value)
                );
            });
        });
    }

    function mostrarStatus(texto, tipo) {
        status.className = `small mb-3 text-${tipo}`;
        status.textContent = texto;
    }
    function atualizarCartaoExcel() {
        if (!metodo || !cartaoContainer || !cartao) return;
        const usaCartao = metodo.value === "Cartão de Crédito";
        cartaoContainer.classList.toggle("d-none", !usaCartao);
        cartao.required = usaCartao;
    }
    if (metodo) metodo.addEventListener("change", atualizarCartaoExcel);
    atualizarCartaoExcel();

    arquivoInput.addEventListener("change", function () {
        arquivoAtual = this.files[0] || null;
        mapeamento.classList.add("d-none");
        botaoImportar.classList.add("d-none");
        mostrarStatus("", "muted");
    });

    botaoPrevia.addEventListener("click", async function () {
        if (!arquivoAtual) {
            mostrarStatus("Selecione um arquivo .xlsx primeiro.", "danger");
            return;
        }
        const dados = new FormData();
        dados.append("arquivo", arquivoAtual);
        botaoPrevia.disabled = true;
        mostrarStatus("Lendo o arquivo e preparando a prévia…", "muted");
        try {
            const resposta = await fetch("/lancamentos/importar/previa", {
                method: "POST",
                body: dados
            });
            const resultado = await resposta.json();
            if (!resposta.ok || !resultado.success) {
                throw new Error(resultado.error || "Não foi possível ler o arquivo.");
            }
            const cabecalho = document.getElementById("excelPreviewHeaders");
            const corpo = document.getElementById("excelPreviewRows");
            cabecalho.replaceChildren();
            corpo.replaceChildren();
            document.querySelectorAll(".excel-column-map").forEach(function (select) {
                const opcaoInicial = select.id === "excel_categoria_col"
                    ? "Usar categoria padrão"
                    : "Selecione uma coluna";
                select.replaceChildren(new Option(opcaoInicial, ""));
                resultado.colunas.forEach(function (coluna) {
                    const rotulo = coluna.nome || "sem título";
                    select.add(new Option(`Coluna ${coluna.indice + 1} · ${rotulo}`, coluna.indice));
                });
            });
            mapearColunasConhecidas(resultado.colunas);
            resultado.colunas.forEach(function (coluna) {
                const th = document.createElement("th");
                th.textContent = coluna.nome || `Coluna ${coluna.indice + 1}`;
                cabecalho.appendChild(th);
            });
            resultado.amostras.forEach(function (linha) {
                const tr = document.createElement("tr");
                resultado.colunas.forEach(function (_, indice) {
                    const td = document.createElement("td");
                    td.textContent = linha[indice] || "";
                    tr.appendChild(td);
                });
                corpo.appendChild(tr);
            });
            document.getElementById("excelPreviewCount").textContent =
                `${resultado.total_linhas} linha(s) com dados encontradas.`;
            mapeamento.classList.remove("d-none");
            botaoImportar.classList.remove("d-none");
            mostrarStatus("Prévia pronta. Confirme as colunas antes de importar.", "success");
        } catch (erro) {
            mostrarStatus(erro.message, "danger");
        } finally {
            botaoPrevia.disabled = false;
        }
    });

    botaoImportar.addEventListener("click", async function () {
        if (!arquivoAtual) {
            mostrarStatus("Selecione o arquivo novamente.", "danger");
            return;
        }
        const campos = ["data", "descricao", "valor"];
        const selecoes = campos.map(campo => document.getElementById(`excel_${campo}_col`));
        const categoriaColuna = document.getElementById("excel_categoria_col");
        if (selecoes.some(select => !select.value) ||
            new Set(selecoes.map(select => select.value)).size !== campos.length) {
            mostrarStatus("Selecione três colunas diferentes para data, nome e preço.", "danger");
            return;
        }
        const colunasSelecionadas = selecoes.map(select => select.value);
        if (categoriaColuna && categoriaColuna.value) {
            if (colunasSelecionadas.includes(categoriaColuna.value)) {
                mostrarStatus("A coluna de categoria precisa ser diferente das demais.", "danger");
                return;
            }
            colunasSelecionadas.push(categoriaColuna.value);
        }
        if (metodo && metodo.value === "Cartão de Crédito" && cartao && !cartao.value) {
            mostrarStatus("Selecione o cartão de crédito utilizado.", "danger");
            return;
        }
        const dados = new FormData();
        dados.append("arquivo", arquivoAtual);
        campos.forEach((campo, indice) => dados.append(`${campo}_col`, selecoes[indice].value));
        dados.append("categoria_col", categoriaColuna ? categoriaColuna.value : "");
        dados.append("categoria", document.getElementById("excel_categoria").value);
        dados.append(
            "formato_decimal",
            document.getElementById("excel_formato_decimal").value
        );
        dados.append("metodo_pagamento", metodo ? metodo.value : "Pix");
        if (cartao) dados.append("cartao_id", cartao.value);
        botaoImportar.disabled = true;
        mostrarStatus("Validando todas as linhas antes de gravar…", "muted");
        try {
            const resposta = await fetch("/lancamentos/importar", {
                method: "POST",
                body: dados
            });
            const resultado = await resposta.json();
            if (!resposta.ok || !resultado.success) {
                const erros = (resultado.erros || []).join(" · ");
                throw new Error([resultado.error, erros].filter(Boolean).join(" "));
            }
            mostrarStatus(resultado.message, "success");
            setTimeout(function () { window.location.reload(); }, 900);
        } catch (erro) {
            mostrarStatus(erro.message, "danger");
            botaoImportar.disabled = false;
        }
    });
}

function setupMetodoPagamentoListener(metodoSelectId, cartaoContainerId, cartaoSelectId, dataInputId, previewContainerId) {
    const metodoSelect = document.getElementById(metodoSelectId);
    const cartaoContainer = document.getElementById(cartaoContainerId);
    const cartaoSelect = document.getElementById(cartaoSelectId);
    const dataInput = document.getElementById(dataInputId);
    const previewContainer = document.getElementById(previewContainerId);

    if (!metodoSelect || !cartaoContainer) return;

    function atualizarVisibilidade() {
        if (metodoSelect.value === "Cartão de Crédito") {
            cartaoContainer.classList.remove("d-none");
            if (cartaoSelect) cartaoSelect.required = true;
            verificarFatura();
        } else {
            cartaoContainer.classList.add("d-none");
            if (cartaoSelect) cartaoSelect.required = false;
            if (previewContainer) {
                previewContainer.innerHTML = "";
                previewContainer.classList.add("d-none");
            }
        }
    }

    function verificarFatura() {
        if (!metodoSelect || metodoSelect.value !== "Cartão de Crédito") return;
        const cid = cartaoSelect ? cartaoSelect.value : null;
        const dt = dataInput ? dataInput.value : null;

        if (!cid || !dt || !previewContainer) return;

        fetch("/api/calcular-fatura", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ data: dt, cartao_id: cid })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                const diaCompra = parseInt(dt.split("-")[2], 10);
                const posFechamento = diaCompra >= data.fechamento_dia;

                let msg = `<div class="alert ${posFechamento ? 'alert-info' : 'alert-light'} border p-2 mb-0 mt-2 small">`;
                msg += `<strong><i class="bi bi-info-circle me-1"></i>Regra de Fatura:</strong> `;
                if (posFechamento) {
                    msg += `Compra feita no dia <strong>${diaCompra}</strong> (após ou no dia do fechamento: <strong>${data.fechamento_dia}</strong>). `;
                    msg += `Esta despesa entra na fatura seguinte, com <strong>vencimento em ${data.data_vencimento_formatada}</strong>.`;
                } else {
                    msg += `Compra feita no dia <strong>${diaCompra}</strong> (antes do fechamento: <strong>${data.fechamento_dia}</strong>). `;
                    msg += `Esta despesa entra na fatura atual, com <strong>vencimento em ${data.data_vencimento_formatada}</strong>.`;
                }
                msg += `</div>`;

                previewContainer.innerHTML = msg;
                previewContainer.classList.remove("d-none");
            }
        })
        .catch(err => console.error("Erro ao calcular fatura:", err));
    }

    metodoSelect.addEventListener("change", atualizarVisibilidade);
    if (cartaoSelect) cartaoSelect.addEventListener("change", verificarFatura);
    if (dataInput) dataInput.addEventListener("change", verificarFatura);

    // Checagem inicial
    atualizarVisibilidade();
}

function setupCalculoParcelas() {
    const totalInput = document.getElementById("parc_valor_total");
    const entradaInput = document.getElementById("parc_entrada");
    const numInput = document.getElementById("parc_num_parcelas");
    const previewDiv = document.getElementById("parc_preview");
    const metodoSelect = document.getElementById("parc_metodo_pagamento");
    const cartaoContainer = document.getElementById("parc_cartao_container");
    const cartaoSelect = document.getElementById("parc_cartao_id");
    const dataInput = document.getElementById("parc_data_compra");

    if (!totalInput || !numInput || !previewDiv) return;

    function atualizarCalculo() {
        const total = parseFloat((totalInput.value || "0").replace(",", ".")) || 0;
        const entrada = parseFloat((entradaInput.value || "0").replace(",", ".")) || 0;
        const nParc = parseInt(numInput.value || "1", 10) || 1;

        const aFinanciar = Math.max(0, total - entrada);
        const valorParc = (aFinanciar / nParc).toFixed(2);

        let html = `<div class="p-2 rounded bg-light border text-secondary small">`;
        html += `<i class="bi bi-calculator me-1 text-primary"></i> `;
        html += `<strong>Simulação:</strong> ${nParc}x de <strong>R$ ${formatarValorBR(valorParc)}</strong>`;
        if (entrada > 0) {
            html += ` (+ R$ ${formatarValorBR(entrada)} de entrada)`;
        }
        html += `</div>`;

        previewDiv.innerHTML = html;
        previewDiv.classList.remove("d-none");
    }

    if (metodoSelect && cartaoContainer) {
        metodoSelect.addEventListener("change", function() {
            if (this.value === "Cartão de Crédito") {
                cartaoContainer.classList.remove("d-none");
                if (cartaoSelect) cartaoSelect.required = true;
            } else {
                cartaoContainer.classList.add("d-none");
                if (cartaoSelect) cartaoSelect.required = false;
            }
        });
    }

    totalInput.addEventListener("input", atualizarCalculo);
    entradaInput.addEventListener("input", atualizarCalculo);
    numInput.addEventListener("input", atualizarCalculo);
    numInput.addEventListener("change", atualizarCalculo);
}

function setupEditarCompraParcelada() {
    const form = document.getElementById("formEditarCompraParcelada");
    const avisoParcelasPagas = document.getElementById("avisoParcelasPagas");
    if (!form || !avisoParcelasPagas) return;

    document.querySelectorAll("[data-edit-compra-parcelada]").forEach(function (botao) {
        botao.addEventListener("click", function () {
            form.action = `/parcelas/editar/${botao.dataset.editId}`;
            document.getElementById("edit_parc_descricao").value =
                botao.dataset.editDescricao || "";
            document.getElementById("edit_parc_data").value =
                botao.dataset.editData || "";
            document.getElementById("edit_parc_valor").value =
                botao.dataset.editValor || "";
            document.getElementById("edit_parc_entrada").value =
                botao.dataset.editEntrada || "0";
            document.getElementById("edit_parc_num").value =
                botao.dataset.editNumParcelas || "1";
            document.getElementById("edit_parc_categoria").value =
                botao.dataset.editCategoria || "";
            document.getElementById("edit_parc_observacao").value =
                botao.dataset.editObservacao || "";

            const metodo = document.getElementById("edit_parc_metodo");
            const cartao = document.getElementById("edit_parc_cartao");
            metodo.value = botao.dataset.editMetodo || "Outro";
            cartao.value = botao.dataset.editCartao || "";
            metodo.dispatchEvent(new Event("change", { bubbles: true }));

            const possuiParcelasPagas =
                Number(botao.dataset.editParcelasPagas || 0) > 0;
            avisoParcelasPagas.classList.toggle("d-none", !possuiParcelasPagas);
            form.querySelectorAll("[data-lock-control]").forEach(function (controle) {
                const chave = controle.dataset.lockControl;
                const oculto = form.querySelector(
                    `[data-lock-value="${chave}"]`
                );
                controle.disabled = possuiParcelasPagas;
                if (oculto) {
                    oculto.disabled = !possuiParcelasPagas;
                    oculto.value = controle.value;
                }
            });

            bootstrap.Modal.getOrCreateInstance(
                document.getElementById("modalEditarCompraParcelada")
            ).show();
        });
    });
}

function setupRecorrentesToggle() {
    const toggles = document.querySelectorAll(".toggle-recorrente-mes");
    toggles.forEach(toggle => {
        toggle.addEventListener("change", function () {
            const recId = this.getAttribute("data-id");
            const anoMes = this.getAttribute("data-mes");
            const ativo = this.checked;
            const toggle = this;

            fetch("/api/recorrentes/toggle", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    recorrente_id: recId,
                    ano_mes: anoMes,
                    ativo: ativo
                })
            })
            .then(res => {
                if (!res.ok) throw new Error("Não foi possível atualizar este mês.");
                return res.json();
            })
            .then(data => {
                if (!data.success) throw new Error(data.error || "Não foi possível atualizar este mês.");
                const status = toggle.parentElement.querySelector("span");
                if (status) status.textContent = ativo ? "Ativo" : "Pausado";
            })
            .catch(err => {
                console.error("Erro ao alterar status recorrente:", err);
                toggle.checked = !ativo;
            });
        });
    });
}

function formatarDataBR(dataStr) {
    if (!dataStr) return "";
    const parts = dataStr.split("-");
    if (parts.length === 3) {
        const data = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
        const formato = document.body.dataset.formatoData || "dd/mm/aaaa";
        if (formato === "extenso") {
            return new Intl.DateTimeFormat("pt-BR", {
                day: "numeric", month: "long", year: "numeric"
            }).format(data);
        }
        if (formato === "semana_extenso") {
            return new Intl.DateTimeFormat("pt-BR", {
                weekday: "long", day: "numeric", month: "long", year: "numeric"
            }).format(data);
        }
        return `${parts[2]}/${parts[1]}/${parts[0]}`;
    }
    return dataStr;
}

function formatarValorBR(valor) {
    return Number(valor).toLocaleString("pt-BR", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
}

// Preenchimento de modal de edição de lançamentos
function preencherModalEdicaoLancamento(id, data, desc, cat, val, met, cid, obs) {
    const form = document.getElementById("formEditarLancamento");
    if (!form) return;
    form.action = `/lancamentos/editar/${id}`;
    document.getElementById("edit_data").value = data;
    document.getElementById("edit_data").dispatchEvent(new Event("change", { bubbles: true }));
    document.getElementById("edit_descricao").value = desc;
    document.getElementById("edit_categoria").value = cat;
    document.getElementById("edit_valor").value = val;
    const metodoSelect = document.getElementById("edit_metodo_pagamento");
    metodoSelect.value = met;
    document.getElementById("edit_observacao").value = obs || "";

    const cartaoSelect = document.getElementById("edit_cartao_id");
    cartaoSelect.value = cid || "";
    metodoSelect.dispatchEvent(new Event("change", { bubbles: true }));

    const editModal = new bootstrap.Modal(document.getElementById("modalEditarLancamento"));
    editModal.show();
}

// Preenchimento de modal de edição de cartões
function preencherModalEdicaoCartao(id, nome, lim, fech, venc, cor, band) {
    const form = document.getElementById("formEditarCartao");
    if (!form) return;
    form.action = `/cartoes/editar/${id}`;
    document.getElementById("edit_cartao_nome").value = nome;
    document.getElementById("edit_cartao_limite").value = lim;
    document.getElementById("edit_cartao_fechamento").value = fech;
    document.getElementById("edit_cartao_vencimento").value = venc;
    document.getElementById("edit_cartao_cor").value = cor;
    const preset = document.getElementById("edit_cartao_cor_preset");
    if (preset) preset.value = Array.from(preset.options).some(function (option) {
        return option.value === cor;
    }) ? cor : "";
    document.getElementById("edit_cartao_bandeira").value = band;

    const editModal = new bootstrap.Modal(document.getElementById("modalEditarCartao"));
    editModal.show();
}

// Preenchimento de modal de edição de recorrente
function preencherModalEdicaoRecorrente(id, desc, val, cat, dia, met, cid) {
    const form = document.getElementById("formEditarRecorrente");
    if (!form) return;
    form.action = `/recorrentes/editar/${id}`;
    document.getElementById("edit_rec_descricao").value = desc;
    document.getElementById("edit_rec_valor").value = formatarValorBR(Number(val));
    document.getElementById("edit_rec_categoria").value = cat;
    document.getElementById("edit_rec_dia").value = dia;
    document.getElementById("edit_rec_metodo").value = met;

    const cartaoContainer = document.getElementById("edit_rec_cartao_container");
    const cartaoSelect = document.getElementById("edit_rec_cartao_id");
    if (met === "Cartão de Crédito") {
        cartaoContainer.classList.remove("d-none");
        if (cid) cartaoSelect.value = cid;
    } else {
        cartaoContainer.classList.add("d-none");
    }

    const editModal = new bootstrap.Modal(document.getElementById("modalEditarRecorrente"));
    editModal.show();
}

// 7. Encerramento seguro: Salvar e Sair OU Sair sem Salvar
function setupSairAplicacao() {
    const btnSairSalvar = document.getElementById("btnConfirmarSair");
    const btnSairSemSalvar = document.getElementById("btnSairSemSalvar");

    function executarEncerramento(salvar) {
        const modalBody = document.getElementById("modalSairBody");
        const modalFooter = document.getElementById("modalSairFooter");

        if (modalBody && modalFooter) {
            modalBody.innerHTML = `
                <div class="text-center py-4">
                    <div class="spinner-border text-dark mb-3" style="width: 2.5rem; height: 2.5rem;" role="status"></div>
                    <h5 class="fw-bold text-dark">${salvar ? 'Salvando alterações e finalizando...' : 'Encerrando sem salvar...'}</h5>
                    <p class="text-muted small mb-0">Desconectando com segurança.</p>
                </div>
            `;
            modalFooter.classList.add("d-none");
        }

        fetch("/api/encerrar", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ salvar: salvar })
        })
        .then(res => res.json())
        .then(data => {
            if (modalBody) {
                modalBody.innerHTML = `
                    <div class="text-center py-4">
                        <div class="mb-3 text-dark fs-1">
                            <i class="bi ${salvar ? 'bi-check-circle-fill text-success' : 'bi-exclamation-circle-fill text-danger'}"></i>
                        </div>
                        <h4 class="fw-bold text-dark mb-1">SmartFinance Finalizado</h4>
                        <p class="text-muted small">${data.message}</p>
                        <div class="p-3 bg-light rounded-3 border text-secondary small mt-3">
                            <i class="bi bi-info-circle me-1"></i>O servidor foi desligado. Você já pode fechar esta janela.
                        </div>
                    </div>
                `;
            }
            setTimeout(function () {
                window.close();
            }, 1000);
        })
        .catch(err => {
            console.error("Erro ao encerrar:", err);
            if (modalBody) {
                modalBody.innerHTML = `
                    <div class="text-center py-3">
                        <h5 class="fw-bold text-dark mb-2">Servidor Finalizado</h5>
                        <p class="text-muted small">Você já pode fechar esta aba do navegador.</p>
                    </div>
                `;
            }
            setTimeout(function () {
                window.close();
            }, 1000);
        });
    }

    if (btnSairSalvar) {
        btnSairSalvar.addEventListener("click", function () {
            executarEncerramento(true);
        });
    }

    if (btnSairSemSalvar) {
        btnSairSemSalvar.addEventListener("click", function () {
            executarEncerramento(false);
        });
    }
}


/**
 * Auto-categorização inteligente:
 * Monitora todos os inputs com [data-cat-target] e chama /api/categorizar com debounce de 400ms.
 * Exibe badge colorido com a sugestão e popula o select automaticamente.
 */
function setupAutoCategorizar() {
    const ORIGENS = {
        "historico_usuario": { label: "Histórico seu", icon: "bi-clock-history", color: "#16a34a" },
        "historico_aproximado": { label: "Histórico aproximado", icon: "bi-search", color: "#2563eb" },
        "regras_inteligentes": { label: "Regra inteligente", icon: "bi-lightning-charge-fill", color: "#d97706" },
        "padrao": { label: "Padrão", icon: "bi-tags", color: "#6b7280" }
    };

    const inputs = document.querySelectorAll("input[data-cat-target]");

    inputs.forEach(function(input) {
        const targetSelectId = input.getAttribute("data-cat-target");
        // Deduzir hint ID: se targetSelectId="modal_categoria" → hintId="modal_cat_hint"
        const hintId = targetSelectId.replace("_categoria", "_cat_hint")
                                     .replace("edit_categoria", "edit_cat_hint");
        const hintEl = document.getElementById(hintId);
        let debounceTimer = null;
        let lastDesc = "";

        input.addEventListener("input", function() {
            const desc = this.value.trim();
            clearTimeout(debounceTimer);

            if (desc.length < 3) {
                if (hintEl) hintEl.innerHTML = "";
                return;
            }
            if (desc === lastDesc) return;

            debounceTimer = setTimeout(function() {
                lastDesc = desc;
                fetch("/api/categorizar", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ descricao: desc })
                })
                .then(r => r.json())
                .then(data => {
                    if (!data.success || !data.categoria) return;

                    const sel = document.getElementById(targetSelectId);
                    if (sel) {
                        for (let opt of sel.options) {
                            if (opt.value === data.categoria) {
                                sel.value = data.categoria;
                                break;
                            }
                        }
                    }

                    if (hintEl) {
                        const meta = ORIGENS[data.origem] || ORIGENS["padrao"];
                        const kw = data.palavra_chave ? ` · "<em>${data.palavra_chave}</em>"` : "";
                        hintEl.innerHTML = `
                            <i class="bi ${meta.icon}" style="color:${meta.color};"></i>
                            <span style="color:${meta.color}; font-weight:700;">${data.categoria}</span>
                            <span class="text-muted">· ${meta.label}${kw}</span>
                        `;
                    }
                })
                .catch(() => {
                    if (hintEl) hintEl.innerHTML = "";
                });
            }, 400);
        });
    });
}
