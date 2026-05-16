import re
from dataclasses import dataclass
from functools import total_ordering

import logger


@total_ordering
@dataclass(frozen=True)
class ParsedUnityVersion:
    major: int
    minor: int
    build: int
    stream: str
    stream_number: int
    raw: str

    @staticmethod
    def parse(version: str) -> "ParsedUnityVersion":
        match = re.match(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?([abcfpx]?)(\d*)$", version)
        if not match:
            raise ValueError(f"Invalid unity version format: {version}")

        major = int(match.group(1) or 0)
        minor = int(match.group(2) or 0)
        build = int(match.group(3) or 0)
        stream = match.group(4) or ""
        stream_number = int(match.group(5) or 0)
        return ParsedUnityVersion(major, minor, build, stream, stream_number, version)

    def to_string_without_type(self) -> str:
        return f"{self.major}.{self.minor}.{self.build}"

    def __str__(self) -> str:
        return self.raw

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ParsedUnityVersion):
            return NotImplemented
        return (
            self.major,
            self.minor,
            self.build,
            self.stream,
            self.stream_number,
        ) == (
            other.major,
            other.minor,
            other.build,
            other.stream,
            other.stream_number,
        )

    def __lt__(self, other: "ParsedUnityVersion") -> bool:
        order = {"": 0, "a": 1, "b": 2, "c": 3, "f": 4, "p": 5, "x": 6}
        return (
            self.major,
            self.minor,
            self.build,
            order.get(self.stream, 0),
            self.stream_number,
        ) < (
            other.major,
            other.minor,
            other.build,
            order.get(other.stream, 0),
            other.stream_number,
        )


class UnityVersion:
    version_table = []
    unity_url = "https://unity3d.com/get-unity/download/archive"

    def __init__(self, fullversion: str, downloadurl: str):
        self.version = ParsedUnityVersion.parse(fullversion)
        self.download_url = None
        self.hash_str = None
        self.use_payload_extraction = False

        downloadurl_splices = downloadurl.split("/")
        if len(downloadurl_splices) <= 4:
            logger.debug_msg(f"{self.version.to_string_without_type()} - {downloadurl}")
            return

        if self.version < ParsedUnityVersion.parse("5.3.99") or downloadurl_splices[4].endswith(".exe"):
            logger.debug_msg(f"{self.version.to_string_without_type()} - {downloadurl}")
            return

        self.use_payload_extraction = True
        self.hash_str = downloadurl_splices[4]
        self.download_url = f"https://download.unity3d.com/download_unity/{self.hash_str}/MacEditorTargetInstaller/UnitySetup-Windows-"
        if self.version >= ParsedUnityVersion.parse("2018.0.0"):
            self.download_url += "Mono-"
        self.download_url += f"Support-for-Editor-{self.version}.pkg"

        logger.debug_msg(f"{self.version.to_string_without_type()} - {self.hash_str} - {self.download_url}")

    @classmethod
    def refresh(cls, web_client) -> None:
        if len(cls.version_table) > 0:
            cls.version_table.clear()

        page_source = web_client.download_string(cls.unity_url)
        if not page_source:
            return

        target = 'unityHubDeepLink\\":\\"unityhub://'

        while True:
            next_index = page_source.find(target)
            if next_index == -1:
                break

            page_source = page_source[next_index + len(target):]
            end_index = page_source.find('\\"')
            if end_index == -1:
                continue

            url = page_source[:end_index]
            parts = url.split("/")
            full_version = parts[0]
            hash_part = parts[1]
            found_url = f"https://download.unity3d.com/download_unity/{hash_part}/Windows64EditorInstaller/UnitySetup64-{full_version}.exe"

            try:
                cls.version_table.append(UnityVersion(full_version, found_url))
            except Exception:
                pass

        cls.version_table.reverse()
