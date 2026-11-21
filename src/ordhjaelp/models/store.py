"""Hent, tjek og slet sprogmodeller (uafhængig af styresystem og brugerflade).

* Stemmer (Piper) hentes direkte fra rhasspy/piper-voices på Hugging Face.
* Talegenkendelse hentes med faster-whisper's egen download-funktion, så den
  lander præcis der, hvor talegenkendelsen leder efter den.
"""

from __future__ import annotations

import contextlib
import io
import logging
import os
import shutil
import threading
import urllib.request
from collections.abc import Callable
from pathlib import Path

from ordhjaelp.models.catalog import Kind, ModelInfo

log = logging.getLogger(__name__)

Progress = Callable[[float], None]  # 0.0 – 1.0
CHUNK = 256 * 1024
# De filer, faster-whisper henter (se faster_whisper.utils.download_model)
SPEECH_FILES = [
    "config.json",
    "preprocessor_config.json",
    "model.bin",
    "tokenizer.json",
    "vocabulary.*",
]


class DownloadCancelled(Exception):
    pass


class ModelStore:
    def __init__(self, voices_dir: Path, speech_dir: Path) -> None:
        self.voices_dir = voices_dir
        self.speech_dir = speech_dir

    # -- status ----------------------------------------------------------
    def is_installed(self, model: ModelInfo) -> bool:
        if model.kind is Kind.VOICE:
            return all(p.exists() for p in self._voice_files(model))
        try:
            from faster_whisper.utils import download_model

            download_model(model.source, cache_dir=str(self.speech_dir), local_files_only=True)
            return True
        except Exception:  # noqa: BLE001 - "ikke hentet" kan se ud på mange måder
            return False

    # -- hent ------------------------------------------------------------
    def download(
        self,
        model: ModelInfo,
        progress: Progress | None = None,
        cancel: threading.Event | None = None,
    ) -> None:
        progress = progress or (lambda _f: None)
        cancel = cancel or threading.Event()
        log.info("Henter %s (%s)", model.title, model.source)
        if model.kind is Kind.VOICE:
            self._download_voice(model, progress, cancel)
        else:
            self._download_speech(model, progress, cancel)
        progress(1.0)
        log.info("%s er hentet", model.title)

    def _voice_files(self, model: ModelInfo) -> list[Path]:
        return [
            self.voices_dir / f"{model.source}.onnx",
            self.voices_dir / f"{model.source}.onnx.json",
        ]

    def _download_voice(
        self, model: ModelInfo, progress: Progress, cancel: threading.Event
    ) -> None:
        from piper.download_voices import URL_FORMAT, VOICE_PATTERN

        match = VOICE_PATTERN.match(model.source)
        if not match:
            raise ValueError(f"Ugyldigt stemmenavn: {model.source}")
        lang_family = match["lang_family"]
        args = {
            "lang_family": lang_family,
            "lang_code": f"{lang_family}_{match['lang_region']}",
            "voice_name": match["voice_name"],
            "voice_quality": match["voice_quality"],
        }
        self.voices_dir.mkdir(parents=True, exist_ok=True)
        total = model.size_mb * 1_000_000
        done = 0
        # Lille config-fil først, så model-filen (den store) styrer statuslinjen
        for extension, target in ((".onnx.json", 1), (".onnx", 0)):
            dest = self._voice_files(model)[target]
            url = URL_FORMAT.format(extension=extension, **args)
            done = _fetch(url, dest, done, total, progress, cancel)

    def _download_speech(
        self, model: ModelInfo, progress: Progress, cancel: threading.Event
    ) -> None:
        # Samme filer og placering som faster-whisper's download_model, men med
        # statuslinje: huggingface_hub melder samlet fremdrift i bytes via tqdm_class.
        from faster_whisper.utils import _MODELS
        from huggingface_hub import snapshot_download

        self.speech_dir.mkdir(parents=True, exist_ok=True)
        snapshot_download(
            _MODELS.get(model.source, model.source),
            cache_dir=str(self.speech_dir),
            allow_patterns=SPEECH_FILES,
            tqdm_class=_progress_tqdm(progress),
        )

    # -- slet ------------------------------------------------------------
    def delete(self, model: ModelInfo) -> None:
        if model.kind is Kind.VOICE:
            for path in self._voice_files(model):
                with contextlib.suppress(FileNotFoundError):
                    path.unlink()
            return
        from faster_whisper.utils import _MODELS
        from huggingface_hub import scan_cache_dir

        repo_id = _MODELS.get(model.source, model.source)
        info = scan_cache_dir(self.speech_dir)
        hashes = [
            rev.commit_hash
            for repo in info.repos
            if repo.repo_id == repo_id
            for rev in repo.revisions
        ]
        if hashes:
            info.delete_revisions(*hashes).execute()
        leftover = self.speech_dir / f"models--{repo_id.replace('/', '--')}"
        shutil.rmtree(leftover, ignore_errors=True)
        log.info("%s er slettet", model.title)


def _fetch(
    url: str, dest: Path, done: int, total: int, progress: Progress, cancel: threading.Event
) -> int:
    part = dest.with_name(dest.name + ".part")
    try:
        with urllib.request.urlopen(url, timeout=30) as response, open(part, "wb") as out:
            while chunk := response.read(CHUNK):
                if cancel.is_set():
                    raise DownloadCancelled
                out.write(chunk)
                done += len(chunk)
                progress(min(0.99, done / total))
        os.replace(part, dest)
    finally:
        with contextlib.suppress(FileNotFoundError):
            part.unlink()
    return done


def _progress_tqdm(progress: Progress):  # noqa: ANN202
    """En tqdm-klasse, der sender fremdrift i bytes videre til `progress`.

    Bemærk: hentningen kan ikke afbrydes herfra – huggingface_hub's xet-overførsel
    kører i sin egen tråd og ignorerer undtagelser fra statuslinjen.
    """
    from tqdm.auto import tqdm

    class ReportingTqdm(tqdm):
        def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
            kwargs["disable"] = False  # skal tælle …
            kwargs["file"] = io.StringIO()  # … men ikke skrive i terminalen
            super().__init__(*args, **kwargs)

        def update(self, n=1):  # noqa: ANN001, ANN201
            result = super().update(n)
            if self.unit == "B" and self.total:
                progress(min(0.99, self.n / self.total))
            return result

    return ReportingTqdm
