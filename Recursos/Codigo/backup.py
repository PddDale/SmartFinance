import hashlib
import json
import math

if __package__:
    from . import database
else:
    import database


TABLES = (
    ("cartoes", "id", "Cartão"),
    ("lancamentos", "id", "Lançamento"),
    ("compras_parceladas", "id", "Compra parcelada"),
    ("parcelas_detalhe", "id", "Parcela"),
    ("gastos_recorrentes", "id", "Gasto recorrente"),
    ("recorrentes_status_mes", "id", "Status recorrente"),
    ("rendas_anuais", "ano", "Renda anual"),
    ("rendas_mensais", "ano_mes", "Renda mensal"),
)


class BackupValidationError(ValueError):
    pass


def _loads_json(raw):
    def reject_constant(value):
        raise ValueError(f"Constante JSON inválida: {value}")

    def reject_duplicate_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("O JSON contém chaves duplicadas.")
            result[key] = value
        return result

    try:
        return json.loads(
            raw.decode("utf-8-sig"),
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise BackupValidationError("O arquivo não contém um JSON válido.") from error


def _validate_backup(backup):
    if not isinstance(backup, dict) or backup.get("versao") != "2.0":
        raise BackupValidationError("Formato de backup não suportado.")

    for section in (
        "configuracoes",
        "saldos",
        "cartoes",
        "lancamentos",
        "compras_parceladas",
        "parcelas_detalhe",
        "gastos_recorrentes",
        "recorrentes_status_mes",
    ):
        if section not in backup:
            raise BackupValidationError(f"O backup não contém a seção '{section}'.")

    config = backup["configuracoes"]
    balances = backup["saldos"]
    if not isinstance(config, dict) or not isinstance(balances, dict):
        raise BackupValidationError("As configurações e os saldos devem ser objetos JSON.")
    required_config = (
        "salario",
        "outras_rendas",
        "ano_ativo",
        "formato_data",
        "renda_variavel_mensal",
        "limites_categoria",
    )
    required_balances = ("conta_corrente", "investimentos")
    if any(key not in config for key in required_config):
        raise BackupValidationError("O backup possui configurações incompletas.")
    if any(key not in balances for key in required_balances):
        raise BackupValidationError("O backup possui saldos incompletos.")
    if (
        isinstance(config["ano_ativo"], bool)
        or not isinstance(config["ano_ativo"], int)
        or not 1 <= config["ano_ativo"] <= 9999
    ):
        raise BackupValidationError("O ano de referência do backup é inválido.")
    if config["formato_data"] not in {
        "dd/mm/aaaa",
        "extenso",
        "semana_extenso",
    }:
        raise BackupValidationError("O formato de data do backup é inválido.")
    if config["renda_variavel_mensal"] not in (0, 1, False, True):
        raise BackupValidationError("A preferência de renda variável é inválida.")
    for value in (
        config["salario"],
        config["outras_rendas"],
        balances["conta_corrente"],
        balances["investimentos"],
    ):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise BackupValidationError("O backup contém valores financeiros inválidos.")
    if not isinstance(config.get("limites_categoria"), dict):
        raise BackupValidationError("A lista de limites por categoria é inválida.")
    for category, limit in config["limites_categoria"].items():
        if (
            not isinstance(category, str)
            or not category.strip()
            or isinstance(limit, bool)
            or not isinstance(limit, (int, float))
            or not math.isfinite(limit)
        ):
            raise BackupValidationError("O backup contém um limite de categoria inválido.")
    if not isinstance(config.get("rendas_anuais", []), list):
        raise BackupValidationError("A lista de rendas anuais é inválida.")
    if not isinstance(config.get("rendas_mensais", []), list):
        raise BackupValidationError("A lista de rendas mensais é inválida.")

    for table, _, _ in TABLES:
        if not isinstance(backup.get(table, []), list):
            raise BackupValidationError(f"A seção '{table}' deve ser uma lista.")
        for record in backup.get(table, []):
            if not isinstance(record, dict):
                raise BackupValidationError(f"Há um registro inválido em '{table}'.")

    for table, _, _ in TABLES:
        records = (
            config.get("rendas_anuais", [])
            if table == "rendas_anuais"
            else config.get("rendas_mensais", [])
            if table == "rendas_mensais"
            else backup.get(table, [])
        )
        for record in records:
            for value in record.values():
                if isinstance(value, (dict, list)):
                    raise BackupValidationError(
                        f"O backup possui um campo inválido em '{table}'."
                    )
                if isinstance(value, float) and not math.isfinite(value):
                    raise BackupValidationError(
                        f"O backup possui um valor numérico inválido em '{table}'."
                    )


def _record_specs(backup):
    config = backup["configuracoes"]
    balances = backup["saldos"]
    config_row = {
        "id": 1,
        "salario": config["salario"],
        "outras_rendas": config["outras_rendas"],
        "saldo_conta_corrente": balances["conta_corrente"],
        "valor_investido": balances["investimentos"],
        "ano_ativo": config["ano_ativo"],
        "formato_data": config["formato_data"],
        "renda_variavel_mensal": config["renda_variavel_mensal"],
    }
    specs = [
        ("configuracoes", "id", "Configurações e saldos", config_row),
    ]

    for category, limit in config["limites_categoria"].items():
        specs.append((
            "limites_categoria",
            "categoria",
            f"Limite da categoria {category}",
            {"categoria": category, "limite_mensal": limit},
        ))

    for table, key, label in TABLES:
        if table == "rendas_anuais":
            records = config.get("rendas_anuais", [])
        elif table == "rendas_mensais":
            records = config.get("rendas_mensais", [])
        else:
            records = backup.get(table, [])
        for record in records:
            specs.append((table, key, f"{label} {record.get(key, '?')}", record))

    seen_keys = set()
    seen_recurring_months = set()
    for table, key_column, _, record in specs:
        identity = (table, record.get(key_column))
        if identity in seen_keys:
            raise BackupValidationError(
                f"O backup possui chaves duplicadas na seção '{table}'."
            )
        seen_keys.add(identity)
        if table == "recorrentes_status_mes":
            recurring_month = (record.get("recorrente_id"), record.get("ano_mes"))
            if recurring_month in seen_recurring_months:
                raise BackupValidationError(
                    "O backup possui mais de um status para a mesma recorrência e mês."
                )
            seen_recurring_months.add(recurring_month)
    return specs


def _table_columns(connection, table):
    return {
        row["name"]
        for row in connection.execute(f'PRAGMA table_info("{table}");').fetchall()
    }


def _find_existing(connection, table, key_column, record):
    key_value = record.get(key_column)
    if key_value is None:
        raise BackupValidationError(f"Falta a chave '{key_column}' em '{table}'.")
    columns = _table_columns(connection, table)
    if key_column not in columns or not set(record).issubset(columns):
        raise BackupValidationError(f"O backup contém campos desconhecidos em '{table}'.")
    table_info = connection.execute(f'PRAGMA table_info("{table}");').fetchall()
    for column in table_info:
        name = column["name"]
        if (
            column["notnull"]
            and column["dflt_value"] is None
            and not column["pk"]
            and (name not in record or record[name] is None)
        ):
            raise BackupValidationError(
                f"O registro de '{table}' está sem o campo obrigatório '{name}'."
            )

    existing = connection.execute(
        f'SELECT * FROM "{table}" WHERE "{key_column}" = ?;',
        (key_value,),
    ).fetchone()
    if existing is None and table == "recorrentes_status_mes":
        if not {"recorrente_id", "ano_mes"}.issubset(record):
            raise BackupValidationError("Um status recorrente está incompleto.")
        existing = connection.execute(
            """
            SELECT * FROM recorrentes_status_mes
            WHERE recorrente_id = ? AND ano_mes = ?;
            """,
            (record["recorrente_id"], record["ano_mes"]),
        ).fetchone()
    return existing


def _find_duplicate_transaction(connection, table, record):
    if table != "lancamentos":
        return None
    comparison_columns = (
        "data",
        "ano_mes",
        "categoria",
        "valor",
        "observacao",
        "metodo_pagamento",
        "cartao_id",
        "fatura_mes",
        "mes_vencimento",
        "data_vencimento",
    )
    if any(column not in record for column in comparison_columns) or "descricao" not in record:
        return None
    clauses = [
        "lower(trim(descricao)) = lower(trim(?))",
        *(f'"{column}" IS ?' for column in comparison_columns),
    ]
    values = [record["descricao"], *(record[column] for column in comparison_columns)]
    return connection.execute(
        "SELECT * FROM lancamentos WHERE "
        + " AND ".join(clauses)
        + " LIMIT 1;",
        values,
    ).fetchone()


def _validate_foreign_keys(connection, backup):
    incoming_records = {
        table: (
            backup["configuracoes"].get("rendas_anuais", [])
            if table == "rendas_anuais"
            else backup["configuracoes"].get("rendas_mensais", [])
            if table == "rendas_mensais"
            else backup.get(table, [])
        )
        for table, _, _ in TABLES
    }
    for table, records in incoming_records.items():
        foreign_keys = connection.execute(
            f'PRAGMA foreign_key_list("{table}");'
        ).fetchall()
        for record in records:
            for foreign_key in foreign_keys:
                value = record.get(foreign_key["from"])
                if value is None:
                    continue
                referenced_table = foreign_key["table"]
                referenced_column = foreign_key["to"]
                in_database = connection.execute(
                    f'SELECT 1 FROM "{referenced_table}" '
                    f'WHERE "{referenced_column}" = ? LIMIT 1;',
                    (value,),
                ).fetchone()
                in_backup = any(
                    incoming.get(referenced_column) == value
                    for incoming in incoming_records.get(referenced_table, [])
                )
                if in_database is None and not in_backup:
                    source_column = foreign_key["from"]
                    raise BackupValidationError(
                        f"O registro de '{table}' referencia um "
                        f"'{referenced_table}' inexistente pelo campo "
                        f"'{source_column}'."
                    )


def _record_matches(existing, incoming):
    return existing is not None and all(
        existing[column] == value for column, value in incoming.items()
    )


def _conflict_id(table, key_column, value):
    identity = json.dumps(
        [table, key_column, value],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def preview_backup(raw):
    backup = _loads_json(raw)
    _validate_backup(backup)

    connection = database.get_db_connection()
    try:
        _validate_foreign_keys(connection, backup)
        new_count = 0
        identical_count = 0
        duplicates = []
        conflicts = []
        fingerprints = {}
        for table, key_column, label, record in _record_specs(backup):
            existing = _find_existing(connection, table, key_column, record)
            if existing is None:
                duplicate = _find_duplicate_transaction(connection, table, record)
                if duplicate is not None:
                    duplicates.append({
                        "label": label,
                        "current": json.dumps(
                            dict(duplicate),
                            ensure_ascii=False,
                            sort_keys=True,
                            default=str,
                        ),
                    })
                    continue
                new_count += 1
            elif _record_matches(existing, record):
                identical_count += 1
            else:
                key_value = record[key_column]
                conflict_id = _conflict_id(table, key_column, key_value)
                current = dict(existing)
                fingerprints[conflict_id] = current
                conflicts.append({
                    "id": conflict_id,
                    "label": label,
                    "current": json.dumps(
                        current, ensure_ascii=False, sort_keys=True, default=str
                    ),
                    "incoming": json.dumps(
                        record, ensure_ascii=False, sort_keys=True, default=str
                    ),
                })
        return {
            "backup": backup,
            "new_count": new_count,
            "identical_count": identical_count,
            "duplicates": duplicates,
            "conflicts": conflicts,
            "fingerprints": fingerprints,
        }
    finally:
        connection.close()


def merge_backup(raw, decisions, expected_fingerprints):
    preview = preview_backup(raw)
    if preview["fingerprints"] != expected_fingerprints:
        raise BackupValidationError(
            "Os dados foram alterados desde a prévia. Gere uma nova prévia antes de importar."
        )
    conflict_ids = set(preview["fingerprints"])
    if set(decisions) != conflict_ids or any(
        choice not in {"current", "incoming"} for choice in decisions.values()
    ):
        raise BackupValidationError("Selecione uma decisão para cada conflito.")

    connection = database.get_db_connection()
    try:
        connection.execute("BEGIN IMMEDIATE;")
        _validate_foreign_keys(connection, preview["backup"])
        current_preview = _preview_with_connection(preview["backup"], connection)
        if current_preview["fingerprints"] != expected_fingerprints:
            raise BackupValidationError(
                "Os dados foram alterados durante a confirmação. Gere uma nova prévia."
            )

        specs = _record_specs(preview["backup"])
        duplicate_keys = {
            (table, record[key_column])
            for table, key_column, _, record in specs
            if _find_existing(connection, table, key_column, record) is None
            and _find_duplicate_transaction(connection, table, record) is not None
        }
        imported_count = 0
        for table, key_column, _, record in specs:
            existing = _find_existing(connection, table, key_column, record)
            if existing is None:
                if (table, record[key_column]) in duplicate_keys:
                    continue
                _insert_record(connection, table, record)
                imported_count += 1
                continue
            if _record_matches(existing, record):
                continue

            conflict_id = _conflict_id(table, key_column, record[key_column])
            if decisions[conflict_id] == "incoming":
                _update_record(connection, table, key_column, record, existing)
                imported_count += 1

        connection.commit()
        return imported_count
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _preview_with_connection(backup, connection):
    new_count = 0
    identical_count = 0
    duplicates = []
    fingerprints = {}
    for table, key_column, label, record in _record_specs(backup):
        existing = _find_existing(connection, table, key_column, record)
        if existing is None:
            duplicate = _find_duplicate_transaction(connection, table, record)
            if duplicate is not None:
                duplicates.append({
                    "label": f"{label} duplicado",
                    "current": dict(duplicate),
                })
                continue
            new_count += 1
        elif _record_matches(existing, record):
            identical_count += 1
        else:
            conflict_id = _conflict_id(table, key_column, record[key_column])
            fingerprints[conflict_id] = dict(existing)
    return {
        "new_count": new_count,
        "identical_count": identical_count,
        "duplicates": duplicates,
        "fingerprints": fingerprints,
    }


def _insert_record(connection, table, record):
    columns = tuple(record)
    placeholders = ", ".join("?" for _ in columns)
    quoted_columns = ", ".join(f'"{column}"' for column in columns)
    connection.execute(
        f'INSERT INTO "{table}" ({quoted_columns}) VALUES ({placeholders});',
        tuple(record[column] for column in columns),
    )


def _update_record(connection, table, key_column, record, existing):
    update_record = dict(record)
    if table == "recorrentes_status_mes" and existing["id"] != record["id"]:
        update_record.pop("id")
        key_column = "id"
        key_value = existing["id"]
    else:
        key_value = record[key_column]
    columns = tuple(column for column in update_record if column != key_column)
    if not columns:
        return
    assignments = ", ".join(f'"{column}" = ?' for column in columns)
    connection.execute(
        f'UPDATE "{table}" SET {assignments} WHERE "{key_column}" = ?;',
        tuple(update_record[column] for column in columns) + (key_value,),
    )
