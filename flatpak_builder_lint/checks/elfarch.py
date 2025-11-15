import glob
import logging
import os
import struct
import tempfile

from .. import builddir, ostree
from . import Check

logger = logging.getLogger(__name__)


def is_elf(fname: str) -> bool:
    if not os.path.isfile(fname):
        return False
    try:
        with open(fname, "br") as f:
            return f.read(4) == b"\x7fELF"
    except OSError as e:
        logger.debug("Failed to read file %s: %s: %s", fname, type(e).__name__, e)
        return False


def find_elf_files(path: str) -> list[str]:
    return [file for file in glob.iglob(f"{path}/**", recursive=True) if is_elf(file)]


def get_elf_arch(fname: str) -> str | None:
    if is_elf(fname):
        try:
            with open(fname, "rb") as f:
                f.seek(18)
                e_machine = struct.unpack("<H", f.read(2))[0]
                arch_map = {
                    0x3E: "x86_64",
                    0xB7: "aarch64",
                    0xF3: "riscv64",
                }
                return arch_map.get(e_machine)
        except struct.error as e:
            logger.debug(
                "Failed to unpack ELF architecture from %s: %s: %s", fname, type(e).__name__, e
            )
        except OSError as e:
            logger.debug("Failed to read ELF file %s: %s: %s", fname, type(e).__name__, e)
    return None


def collect_elf_arches(path: str) -> dict[str, str]:
    return {file: arch for file in find_elf_files(path) if (arch := get_elf_arch(file)) is not None}


class ELFArchCheck(Check):
    def _validate(self, path: str, ref: str) -> None:
        splits = ref.split("/")
        ref_arch = splits[1]

        elf_arches_dict: dict[str, str] = {}

        for subpath in ("files/lib", "files/bin"):
            fullpath = os.path.join(path, subpath)
            elf_arches_dict.update(collect_elf_arches(fullpath))

        elf_arches = elf_arches_dict.values()

        if not (elf_arches_dict and elf_arches):
            return

        if len(set(elf_arches)) >= 2:
            self.errors.add("elf-arch-multiple-found")
            self.info.add(f"elf-arch-multiple-found: {list(elf_arches)}")

        if ref_arch not in elf_arches:
            self.errors.add("elf-arch-not-found")
            self.info.add(
                f"elf-arch-not-found: Ref arch is {ref_arch} but collected ELF arch is"
                + f" {list(elf_arches)}, {elf_arches_dict}"
            )

    def check_build(self, path: str) -> None:
        stripped_ref = builddir.get_runtime(path)
        if not stripped_ref:
            return

        self._validate(path, stripped_ref)

    def check_repo(self, path: str) -> None:
        return
        self._populate_refs(path)
        refs = self.repo_primary_refs
        if not refs:
            return

        for ref in refs:
            stripped_ref = "/".join(ref.split("/")[1:])

            with tempfile.TemporaryDirectory() as tmpdir:
                for subdir in ("bin", "lib"):
                    os.makedirs(os.path.join(tmpdir, subdir), exist_ok=True)
                    ostree.extract_subpath(
                        path, ref, f"files/{subdir}", os.path.join(tmpdir, subdir), True
                    )

                self._validate(tmpdir, stripped_ref)
