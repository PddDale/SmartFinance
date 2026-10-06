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

    // 3. Monitoramento dinâmico de Método de Pagamento e Cartão (Formulário de Lançamento)
    setupMetodoPagamentoListener("metodo_pagamento", "cartao_container", "cartao_id", "data_lancamento", "fatura_preview");
    setupMetodoPagamentoListener("modal_metodo_pagamento", "modal_cartao_container", "modal_cartao_id", "modal_data_lancamento", "modal_fatura_preview");

    // 4. Cálculo dinâmico de parcelas no modal de Compra Parcelada
    setupCalculoParcelas();

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
});

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

            const valor = Number(this.value);
            correspondente.value = this.value === "" || !Number.isFinite(valor)
                ? ""
                : (anual ? valor / 12 : valor * 12).toFixed(2);
            if (modoInput) modoInput.value = anual ? "anual" : "mensal";
        });
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
                    msg += `Esta despesa entra na fatura seguinte, com <strong>vencimento em ${formatarDataBR(data.data_vencimento)}</strong>.`;
                } else {
                    msg += `Compra feita no dia <strong>${diaCompra}</strong> (antes do fechamento: <strong>${data.fechamento_dia}</strong>). `;
                    msg += `Esta despesa entra na fatura atual, com <strong>vencimento em ${formatarDataBR(data.data_vencimento)}</strong>.`;
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
        html += `<strong>Simulação:</strong> ${nParc}x de <strong>R$ ${valorParc.replace(".", ",")}</strong>`;
        if (entrada > 0) {
            html += ` (+ R$ ${entrada.toFixed(2).replace(".", ",")} de entrada)`;
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

function setupRecorrentesToggle() {
    const toggles = document.querySelectorAll(".toggle-recorrente-mes");
    toggles.forEach(toggle => {
        toggle.addEventListener("change", function () {
            const recId = this.getAttribute("data-id");
            const anoMes = this.getAttribute("data-mes");
            const ativo = this.checked;

            fetch("/api/recorrentes/toggle", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    recorrente_id: recId,
                    ano_mes: anoMes,
                    ativo: ativo
                })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    const row = document.getElementById(`recorrente-row-${recId}`);
                    if (row) {
                        if (ativo) {
                            row.classList.remove("opacity-50", "table-light");
                        } else {
                            row.classList.add("opacity-50", "table-light");
                        }
                    }
                }
            })
            .catch(err => {
                console.error("Erro ao alterar status recorrente:", err);
                // Reverter switch em caso de erro
                this.checked = !ativo;
            });
        });
    });
}

function formatarDataBR(dataStr) {
    if (!dataStr) return "";
    const parts = dataStr.split("-");
    if (parts.length === 3) return `${parts[2]}/${parts[1]}/${parts[0]}`;
    return dataStr;
}

// Preenchimento de modal de edição de lançamentos
function preencherModalEdicaoLancamento(id, data, desc, cat, val, met, cid, obs) {
    const form = document.getElementById("formEditarLancamento");
    if (!form) return;
    form.action = `/lancamentos/editar/${id}`;
    document.getElementById("edit_data").value = data;
    document.getElementById("edit_descricao").value = desc;
    document.getElementById("edit_categoria").value = cat;
    document.getElementById("edit_valor").value = val;
    document.getElementById("edit_metodo_pagamento").value = met;
    document.getElementById("edit_observacao").value = obs || "";

    const cartaoContainer = document.getElementById("edit_cartao_container");
    const cartaoSelect = document.getElementById("edit_cartao_id");

    if (met === "Cartão de Crédito") {
        cartaoContainer.classList.remove("d-none");
        if (cid) cartaoSelect.value = cid;
    } else {
        cartaoContainer.classList.add("d-none");
    }

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
    document.getElementById("edit_rec_valor").value = val;
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
