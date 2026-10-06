@echo off
cd /d "%~dp0"
title SmartFinance - Controle Financeiro Pessoal
echo ================================================================
echo                   INICIANDO SMARTFINANCE
echo ================================================================
echo.
echo Verificando dependencias Python...
py -m pip install --upgrade -r "Recursos\Dependencias\requirements.txt"
if errorlevel 1 (
    echo.
    echo Nao foi possivel instalar ou atualizar as dependencias do Python.
    echo Verifique a conexao com a internet e as permissoes de escrita
    echo na instalacao global do Python.
    echo Se necessario, execute este arquivo como administrador.
    pause
    exit /b 1
)
echo.
echo Iniciando aplicacao web...
echo Acesse no seu navegador: http://127.0.0.1:5000
echo Pressione CTRL+C ou utilize o botao "Sair" na aplicacao para fechar.
echo.
start http://127.0.0.1:5000
py "Recursos\Codigo\app.py"
if %errorlevel% neq 0 (
    echo.
    echo Ocorreu um erro ao executar a aplicacao.
    pause
)
exit
