import shutil
import sys
import time
from enum import Enum
from pathlib import Path
from urllib.request import Request, urlopen

import logger
from archive_handler import ArchiveHandler
from unity_version import ParsedUnityVersion, UnityVersion


class WebClient:
    def __init__(self):
        self.headers = {"User-Agent": "Unity web player"}

    def download_string(self, url: str) -> str:
        request = Request(url, headers=self.headers)
        with urlopen(request) as response:
            return response.read().decode("utf-8", errors="ignore")

    def download_file(self, url: str, output_path: str) -> None:
        request = Request(url, headers=self.headers)
        with urlopen(request) as response, open(output_path, "wb") as out_file:
            shutil.copyfileobj(response, out_file)


class OperationModes(Enum):
    Normal = 0
    Android_Il2Cpp = 1
    Android_Mono = 2


BASE_DIR = Path(__file__).resolve().parent
web_client = WebClient()
cache_path = None
temp_folder_path = None
cooldown_interval = 5
operation_mode = OperationModes.Normal


def get_unity_version_from_string(requested_version: str):
    for version in UnityVersion.version_table:
        if version.version.raw == requested_version or version.version.to_string_without_type() == requested_version:
            return version
    return None


def version_filter(version, should_error: bool = True) -> bool:
    if operation_mode in (OperationModes.Android_Il2Cpp, OperationModes.Android_Mono):
        if version.version <= ParsedUnityVersion.parse("5.2.99"):
            if should_error:
                logger.error(f"{version.version} Has No Android Support Installer!")
            else:
                logger.warning(f"{version.version} Has No Android Support Installer!")
            return False
    return True


def process_specific(requested_version: str) -> bool:
    version = get_unity_version_from_string(requested_version)
    if version is None:
        logger.error(f"Failed to Find Unity Version [{requested_version}] in List!")
        return False
    return process_unity_version(version)


def process_all() -> bool:
    sorted_version_table = []
    for version in UnityVersion.version_table:
        if not version_filter(version, False):
            continue

        zip_path = BASE_DIR / f"{version.version.to_string_without_type()}.zip"
        if zip_path.exists():
            logger.warning(f"{version.version} Zip Already Exists! Skipping...")
            continue

        logger.msg(f"{version.version} Zip Doesn't Exist! Adding to Download List...")
        sorted_version_table.append(version)

    sorted_version_table.reverse()

    error_count = 0
    if len(sorted_version_table) >= 1:
        success_count = 0
        for version in sorted_version_table:
            if process_unity_version(version):
                success_count += 1
            else:
                logger.warning("Failure Detected! Skipping to Next Version...")
                error_count += 1

            logger.msg(f"Cooldown Active for {cooldown_interval} seconds...")
            time.sleep(cooldown_interval)

        if error_count > 0:
            logger.error(f"{error_count} Failures")

        if success_count > 0:
            logger.msg(f"{success_count} Successful Zip Creations")

    return error_count <= 0


def extract_files_from_archive(version) -> bool:
    global cache_path

    internal_path = None
    archive_path = cache_path

    if version.use_payload_extraction:
        logger.msg("Extracting Payload...")
        if not ArchiveHandler.extract_files(str(BASE_DIR), archive_path, "Payload~"):
            return False
        archive_path = str(BASE_DIR / "Payload~")

    if operation_mode == OperationModes.Normal:
        if version.version < ParsedUnityVersion.parse("4.5.0"):
            internal_path = "Data/PlaybackEngines/windows64standaloneplayer/"
        elif version.version < ParsedUnityVersion.parse("5.0.0"):
            internal_path = "Data/PlaybackEngines/windowsstandalonesupport/Variations/win64_nondevelopment/Data/"
        elif version.version < ParsedUnityVersion.parse("5.3.0"):
            internal_path = "./Unity/Unity.app/Contents/PlaybackEngines/WindowsStandaloneSupport/Variations/win64_nondevelopment_mono/Data/"
        elif version.version < ParsedUnityVersion.parse("2021.2"):
            internal_path = "./Variations/win64_player_nondevelopment_mono/Data/"
        else:
            internal_path = "./Variations/win64_nondevelopment_mono/Data/"

        logger.msg("Extracting DLLs from Archive...")
        return ArchiveHandler.extract_files(temp_folder_path, archive_path, internal_path + "Managed/*.dll")

    rootpath = "$INSTDIR$*"
    basefolder = f"{rootpath}/Variations/{'il2cpp' if operation_mode == OperationModes.Android_Il2Cpp else 'mono'}/"
    libfilename = "libunity.so"

    if version.use_payload_extraction:
        rootpath = "./Variations"
        basefolder = f"{rootpath}/{'il2cpp' if operation_mode == OperationModes.Android_Il2Cpp else 'mono'}/"

    logger.msg(f"Extracting {libfilename} from Archive...")
    if not ArchiveHandler.extract_files(temp_folder_path, archive_path, f"{basefolder}Release/Libs/*/{libfilename}", True):
        return False

    logger.msg("Fixing Folder Structure...")
    libs_folder_path = Path(temp_folder_path) / "Libs"
    if not libs_folder_path.exists():
        libs_folder_path.mkdir(parents=True, exist_ok=True)

    for filepath in Path(temp_folder_path).rglob(libfilename):
        logger.msg(f"Moving {filepath}")
        parent_name = filepath.parent.name
        new_path = libs_folder_path / parent_name
        if not new_path.exists():
            new_path.mkdir(parents=True, exist_ok=True)
        shutil.move(str(filepath), str(new_path / filepath.name))

    root_folders = list(Path(temp_folder_path).glob(rootpath))
    if len(root_folders) <= 0:
        logger.error(f"Failed to Find Root Folder with Pattern: {rootpath}")
        return False
    root_folder = root_folders[0]
    logger.msg(f"Removing {root_folder}")
    shutil.rmtree(root_folder)

    logger.msg("Extracting Managed Folder...")
    new_managed_folder = Path(temp_folder_path) / "Managed"
    if not new_managed_folder.exists():
        new_managed_folder.mkdir(parents=True, exist_ok=True)

    return ArchiveHandler.extract_files(str(new_managed_folder), archive_path, basefolder + "Managed/*.dll")


def process_unity_version(version) -> bool:
    global cache_path, temp_folder_path

    if not version_filter(version):
        return False

    zip_path = BASE_DIR / f"{version.version.to_string_without_type()}.zip"
    if zip_path.exists():
        zip_path.unlink()

    downloadurl = version.download_url
    if operation_mode in (OperationModes.Android_Il2Cpp, OperationModes.Android_Mono):
        downloadurl = downloadurl[: downloadurl.rfind("/")]
        if version.use_payload_extraction:
            downloadurl = f"{downloadurl[:downloadurl.rfind('/')]}/MacEditorTargetInstaller/UnitySetup-Android-Support-for-Editor-{version.version}.pkg"
        else:
            downloadurl = f"{downloadurl[:downloadurl.rfind('/')]}/TargetSupportInstaller/UnitySetup-Android-Support-for-Editor-{version.version}.exe"

    logger.msg(f"Downloading {downloadurl}")
    was_error = False

    try:
        web_client.download_file(downloadurl, cache_path)
        was_error = not extract_files_from_archive(version)
        time.sleep(1)
        if not was_error:
            ArchiveHandler.create_zip(temp_folder_path, str(zip_path))
    except Exception as exc:
        logger.error(str(exc))
        was_error = True

    logger.msg("Cleaning up...")
    temp_path = Path(temp_folder_path)
    if temp_path.exists():
        shutil.rmtree(temp_path)

    cache_file = Path(cache_path)
    if cache_file.exists():
        cache_file.unlink()

    payload_path = BASE_DIR / "Payload~"
    if payload_path.exists():
        if payload_path.is_dir():
            shutil.rmtree(payload_path)
        else:
            payload_path.unlink()

    if was_error:
        return False

    logger.msg(f"{version.version.to_string_without_type()} Zip Successfully Created!")
    return True


def program_main(args) -> int:
    global cache_path, temp_folder_path, operation_mode

    temp_folder_path = str(BASE_DIR / "tmp")
    temp_path = Path(temp_folder_path)
    if temp_path.exists():
        shutil.rmtree(temp_path)

    cache_path = str(BASE_DIR / "cache.tmp")
    cache_file = Path(cache_path)
    if cache_file.exists():
        cache_file.unlink()

    if len(args) < 1 or len(args) > 2 or not args[0]:
        logger.error("Bad arguments for extractor process; expected arguments: <unityVersion>")
        return -1

    requested_version = args[0]

    if requested_version.endswith(";android") or requested_version.endswith(";android_il2cpp"):
        operation_mode = OperationModes.Android_Il2Cpp
    elif requested_version.endswith(";android_mono"):
        operation_mode = OperationModes.Android_Mono
    else:
        operation_mode = OperationModes.Normal

    if operation_mode != OperationModes.Normal:
        requested_version = requested_version[: requested_version.rfind(";")]

    UnityVersion.refresh(web_client)
    if len(UnityVersion.version_table) <= 0:
        logger.error(f"Failed to Get Unity Versions List from {UnityVersion.unity_url}")
        return -1

    if len(args) == 2 and args[1]:
        version = get_unity_version_from_string(requested_version)
        if version is None:
            logger.error(f"Failed to Find Unity Version [{requested_version}] in List!")
            return -1

        cache_path = args[1]
        try:
            return 0 if extract_files_from_archive(version) else -1
        except Exception as exc:
            logger.error(str(exc))
            return -1

    if requested_version.startswith("--all"):
        return 0 if process_all() else -1

    return 0 if process_specific(requested_version) else -1


if __name__ == "__main__":
    raise SystemExit(program_main(sys.argv[1:]))
