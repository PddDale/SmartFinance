@echo off
title SmartFinance - Controle Financeiro Pessoal
echo ================================================================
echo                   INICIANDO SMARTFINANCE
echo ================================================================
echo.
echo Verificando dependencias Python...
py -m pip install -r requirements.txt --quiet
echo.
echo Iniciando aplicacao web...
echo Acesse no seu navegador: http://127.0.0.1:5000
echo Pressione CTRL+C ou utilize o botao "Sair" na aplicacao para fechar.
echo.
start http://127.0.0.1:5000
py app.py
if %errorlevel% neq 0 (
    echo.
    echo Ocorreu um erro ao executar a aplicacao.
    pause
)
exit
