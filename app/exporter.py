from __future__ import annotations

from pathlib import Path

from .dnflib_io import DnflibNpkIO
from .models import ExportJob, ExportReport
from .npk_paths import (
    normalize_img_path,
    resolve_source_npk,
    should_skip_export_img,
    skill_output_filename,
)


class NpkExporter:
    def __init__(self, npk_io=None):
        self._npk_io = npk_io or DnflibNpkIO()

    def export_skill(self, job: ExportJob) -> ExportReport:
        output_name = job.output_name or skill_output_filename(job.skill.chinese_name)
        output_path = job.output_dir / output_name
        if output_path.exists() and not job.overwrite:
            raise FileExistsError(f"Output already exists: {output_path}")

        seen: set[str] = set()
        entries: list[tuple[str, bytes]] = []
        source_npks: list[Path] = []
        for raw_img_path in job.skill.img_paths:
            img_path = normalize_img_path(raw_img_path)
            if not img_path or img_path in seen:
                continue
            seen.add(img_path)
            if not job.include_icon and img_path == normalize_img_path(job.skill.icon_img_path):
                continue
            if should_skip_export_img(
                img_path,
                include_icon=job.include_icon,
                include_body_templates=job.include_body_templates,
            ):
                continue
            source_npk = resolve_source_npk(job.source_dir, img_path)
            if not source_npk.exists():
                raise FileNotFoundError(f"Missing source NPK {source_npk.name} for IMG {img_path}")
            data = self._npk_io.read_entry(source_npk, img_path)
            entries.append((img_path, data))
            if source_npk not in source_npks:
                source_npks.append(source_npk)

        self._npk_io.write_npk(output_path, entries, job.overwrite)
        return ExportReport(
            skill=job.skill,
            output_path=output_path,
            entry_count=len(entries),
            byte_count=sum(len(data) for _path, data in entries),
            source_npks=tuple(source_npks),
        )

    def missing_source_npks(
        self,
        skill,
        source_dir: Path,
        *,
        include_icon: bool = False,
        include_body_templates: bool = False,
    ) -> list[str]:
        missing: list[str] = []
        seen: set[str] = set()
        for raw_img_path in skill.img_paths:
            img_path = normalize_img_path(raw_img_path)
            if not img_path or img_path in seen:
                continue
            seen.add(img_path)
            if not include_icon and img_path == normalize_img_path(skill.icon_img_path):
                continue
            if should_skip_export_img(
                img_path,
                include_icon=include_icon,
                include_body_templates=include_body_templates,
            ):
                continue
            source_npk = resolve_source_npk(source_dir, img_path)
            if not source_npk.exists() and source_npk.name not in missing:
                missing.append(source_npk.name)
        return missing
