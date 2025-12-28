#!/usr/bin/env python3
"""
Type Checking Script - Jewelry Invoice Bot
===========================================

Script para verificación de tipos con diferentes niveles de estrictez.

Uso:
    python scripts/typecheck.py              # Modo CI (usa pyproject.toml)
    python scripts/typecheck.py --strict     # Modo estricto (todos los errores)
    python scripts/typecheck.py --report     # Genera reporte detallado
    python scripts/typecheck.py --module src/core  # Verifica módulo específico

Niveles de verificación:
    - CI: Usa pyproject.toml (errores ignorados en módulos legacy)
    - Strict: Muestra TODOS los errores sin ignorar ninguno
    - Report: Genera reporte con estadísticas por archivo

Este script es parte del plan de migración gradual a MyPy estricto.
"""

import argparse
import subprocess
import sys
import re
from collections import Counter
from pathlib import Path
from typing import NamedTuple


class TypeCheckResult(NamedTuple):
    """Resultado de la verificación de tipos."""
    success: bool
    total_errors: int
    files_with_errors: int
    errors_by_file: dict[str, int]
    errors_by_type: dict[str, int]
    output: str


def run_mypy(
    path: str = "src/",
    config_file: str | None = None,
    strict: bool = False,
) -> TypeCheckResult:
    """
    Ejecuta MyPy y parsea los resultados.

    Args:
        path: Ruta a verificar
        config_file: Archivo de configuración (None para modo estricto)
        strict: Si True, ignora pyproject.toml y usa configuración estricta

    Returns:
        TypeCheckResult con los resultados
    """
    cmd = ["python", "-m", "mypy", path]

    if strict:
        # Modo estricto: sin ignorar errores
        cmd.extend([
            "--ignore-missing-imports",
            "--show-error-codes",
            "--pretty",
        ])
    elif config_file:
        cmd.extend(["--config-file", config_file])
    else:
        cmd.extend(["--config-file", "pyproject.toml"])

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent,
    )

    output = result.stdout + result.stderr

    # Parsear errores por archivo
    file_pattern = r"^(src[^:]+):"
    files = re.findall(file_pattern, output, re.MULTILINE)
    errors_by_file = dict(Counter(files))

    # Parsear tipos de errores
    type_pattern = r"\[([a-z\-]+)\]"
    error_types = re.findall(type_pattern, output)
    errors_by_type = dict(Counter(error_types))

    total_errors = sum(errors_by_file.values())
    files_with_errors = len(errors_by_file)

    success = result.returncode == 0 and total_errors == 0

    return TypeCheckResult(
        success=success,
        total_errors=total_errors,
        files_with_errors=files_with_errors,
        errors_by_file=errors_by_file,
        errors_by_type=errors_by_type,
        output=output,
    )


def print_report(result: TypeCheckResult, verbose: bool = False) -> None:
    """Imprime un reporte formateado de los resultados."""
    print("=" * 70)
    print("REPORTE DE VERIFICACION DE TIPOS")
    print("=" * 70)
    print()

    if result.success:
        print("[OK] Estado: PASO - Sin errores de tipos")
    else:
        print(f"[ERROR] Estado: FALLO - {result.total_errors} errores encontrados")

    print()
    print("-" * 70)
    print("RESUMEN")
    print("-" * 70)
    print(f"  Total de errores:     {result.total_errors}")
    print(f"  Archivos afectados:   {result.files_with_errors}")
    print(f"  Tipos de errores:     {len(result.errors_by_type)}")

    if result.errors_by_type:
        print()
        print("-" * 70)
        print("ERRORES POR TIPO")
        print("-" * 70)
        for error_type, count in sorted(
            result.errors_by_type.items(),
            key=lambda x: -x[1]
        ):
            print(f"  [{error_type}]: {count}")

    if result.errors_by_file:
        print()
        print("-" * 70)
        print("ERRORES POR ARCHIVO")
        print("-" * 70)
        for file, count in sorted(
            result.errors_by_file.items(),
            key=lambda x: -x[1]
        ):
            print(f"  {count:4d} - {file}")

    if verbose and result.output:
        print()
        print("-" * 70)
        print("DETALLE DE ERRORES")
        print("-" * 70)
        print(result.output)

    print()
    print("=" * 70)


def main() -> int:
    """Punto de entrada principal."""
    parser = argparse.ArgumentParser(
        description="Verificación de tipos para Jewelry Invoice Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--strict",
        action="store_true",
        help="Modo estricto: muestra TODOS los errores sin ignorar",
    )

    parser.add_argument(
        "--report",
        action="store_true",
        help="Genera reporte detallado con estadísticas",
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Muestra todos los errores en detalle",
    )

    parser.add_argument(
        "--module",
        type=str,
        default="src/",
        help="Módulo específico a verificar (default: src/)",
    )

    parser.add_argument(
        "--ci",
        action="store_true",
        help="Modo CI: falla si hay errores no ignorados",
    )

    args = parser.parse_args()

    print()
    print("Ejecutando verificacion de tipos...")
    print(f"   Modulo: {args.module}")
    print(f"   Modo: {'Estricto' if args.strict else 'CI (pyproject.toml)'}")
    print()

    result = run_mypy(
        path=args.module,
        strict=args.strict,
    )

    if args.report or args.verbose:
        print_report(result, verbose=args.verbose)
    elif result.success:
        print("[OK] Verificacion de tipos exitosa - Sin errores")
    else:
        print(f"[ERROR] {result.total_errors} errores en {result.files_with_errors} archivos")

        if not args.strict:
            print()
            print("Tip: Ejecuta con --strict para ver todos los errores")
            print("Tip: Ejecuta con --report para ver estadisticas detalladas")

    # En modo CI, retornar código de error si falló
    if args.ci and not result.success:
        return 1

    # En modo estricto, mostrar errores pero no fallar (es informativo)
    if args.strict:
        return 0

    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
