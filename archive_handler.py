import subprocess
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

import logger


BASE_DIR = Path(__file__).resolve().parent


class ArchiveHandler:
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
        seven_zip = BASE_DIR / "7z" / "7z.exe"
        args = [
            str(seven_zip),
            "x" if keep_file_path else "e",
            str(archive_path),
            "-y",
            f"-o{output_path}",
            str(internal_path),
        ]

        logger.debug_msg("\"" + str(seven_zip) + "\" " + " ".join(args[1:]))

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
