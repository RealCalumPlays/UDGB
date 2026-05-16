import subprocess
import platform
import shutil
from typing import Optional
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

import logger


BASE_DIR = Path(__file__).resolve().parent


class ArchiveHandler:
    @staticmethod
    def _resolve_seven_zip() -> Optional[str]:
        if platform.system() == "Linux":
            seven_zip = shutil.which("7z")
            if not seven_zip:
                logger.error(
                    "7z binary not found in PATH. Install 7z or p7zip (e.g. sudo apt install p7zip-full)."
                )
            return seven_zip

        seven_zip = BASE_DIR / "7z" / "7z.exe"
        if not seven_zip.exists():
            logger.error(f"Bundled 7z binary was not found at: {seven_zip}")
            return None
        return str(seven_zip)

    @staticmethod
    def create_zip(input_folder: str, output_file: str) -> None:
        output_path = Path(output_file)
        if output_path.exists():
            output_path.unlink()

        input_path = Path(input_folder)
        with ZipFile(output_path, "w", ZIP_DEFLATED) as zip_file:
            for file_path in input_path.rglob("*"):
                if file_path.is_file():
                    zip_file.write(file_path, file_path.relative_to(input_path))

    @staticmethod
    def extract_files(output_path: str, archive_path: str, internal_path: str, keep_file_path: bool = False) -> bool:
        seven_zip = ArchiveHandler._resolve_seven_zip()
        if not seven_zip:
            return False

        args = [
            seven_zip,
            "x" if keep_file_path else "e",
            str(archive_path),
            "-y",
            f"-o{output_path}",
            str(internal_path),
        ]

        logger.debug_msg("\"" + seven_zip + "\" " + " ".join(args[1:]))

        process = subprocess.Popen(
            args,
            cwd=str(BASE_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = process.communicate()

        if stdout:
            for line in stdout.splitlines():
                logger.msg(line)

        if stderr:
            for line in stderr.splitlines():
                logger.error(line)

        return process.returncode == 0
