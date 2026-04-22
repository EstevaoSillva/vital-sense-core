import csv
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from employee.models import EmployeeRecord

User = get_user_model()


class Command(BaseCommand):
    help = "Importa usuarios e perfis de employee a partir de CSV."

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            dest="csv_path",
            default="TreinandoHarvardRev01/employeedataset.csv",
            help="Caminho para o CSV (default: TreinandoHarvardRev01/employeedataset.csv)",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Remove employee records e usuarios importados antes de importar.",
        )
        parser.add_argument(
            "--default-password",
            dest="default_password",
            default="ChangeMe123!",
            help="Senha padrao para usuarios importados.",
        )
        parser.add_argument(
            "--username-prefix",
            dest="username_prefix",
            default="imported.employee",
            help="Prefixo usado para gerar username.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        csv_path = Path(options["csv_path"]).resolve()
        if not csv_path.exists():
            raise CommandError(f"CSV nao encontrado: {csv_path}")

        if options["clear"]:
            imported_users = User.objects.filter(username__startswith=f"{options['username_prefix']}.")
            EmployeeRecord.objects.filter(user__in=imported_users).delete()
            imported_users.delete()

        created_users = 0
        created_employees = 0
        updated_users = 0

        with csv_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for index, row in enumerate(reader, start=1):
                seed = (row.get("Employee ID") or "").strip() or f"{index}"
                username = _make_unique_username(options["username_prefix"], seed)
                name = f"Imported Employee {index}"
                email = f"{username}@import.local"

                user, was_created = User.objects.get_or_create(
                    username=username,
                    defaults={
                        "password": "",
                        "name": name,
                        "email": email,
                        "is_active": True,
                    },
                )
                if was_created:
                    user.set_password(options["default_password"])
                    user.save(update_fields=["password"])
                    created_users += 1
                else:
                    changed = False
                    if not user.email:
                        user.email = email
                        changed = True
                    if changed:
                        user.save(update_fields=["email", "modified_at"])
                        updated_users += 1

                _, employee_created = EmployeeRecord.objects.get_or_create(user=user)
                if employee_created:
                    created_employees += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Importacao concluida. "
                f"Usuarios criados: {created_users}, "
                f"usuarios atualizados: {updated_users}, "
                f"employees criados: {created_employees}"
            )
        )


def _make_unique_username(prefix: str, seed: str) -> str:
    base_seed = "".join(ch.lower() if ch.isalnum() else "." for ch in seed).strip(".")
    base_seed = ".".join(part for part in base_seed.split(".") if part)
    if not base_seed:
        base_seed = "user"

    base_username = f"{prefix}.{base_seed}"[:64]
    username = base_username
    suffix = 1
    while User.objects.filter(username=username).exists():
        suffix_text = f".{suffix}"
        username = f"{base_username[: 64 - len(suffix_text)]}{suffix_text}"
        suffix += 1
    return username
