from __future__ import annotations

import base64
import hashlib
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
import sys
sys.path.insert(0, str(SCRIPTS))

from asset_manifest_audit import audit_repository  # noqa: E402
from asset_manifest_core import (  # noqa: E402
    ManifestError,
    compute_audio_generation_identity,
    map_audio_legacy,
    validate_manifest,
)

TINY_MP3_B64 = (
    "SUQzBAAAAAAAIlRTU0UAAAAOAAADTGF2ZjYxLjcuMTAzAAAAAAAAAAAAAAD/40jAAAAAAAAAAAAASW5mbwAAAA8AAAAEAAAF"
    "oABmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmaZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZmZzMzMzMzMzMzMzMzMzMzMzMz"
    "MzMzMzMzMzP////////////////////////////////8AAAAATGF2YzYxLjE5AAAAAAAAAAAAAAAAJAMAAAAAAAAABaDnpp+FAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD/40jEAAAAA0gAAAAATEFNRTMuMTAwVVVVVVVVVVVVVVVMQU1FMy4xMDBVVVVVVVVV"
    "VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
    "VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
    "VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVX"
    "/40jEAAAAA0gAAAAATEFNRTMuMTAwVVVVVVVVVVVVVVVMQU1FMy4xMDBVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
    "VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
    "VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
    "VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVX"
    "/40jEAAAAA0gAAAAATEFNRTMuMTAwVVVVVVVVVVVVVVVMQU1FMy4xMDBVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
    "VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
    "VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
    "VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVX"
    "/40jEAAAAA0gAAAAATEFNRTMuMTAwVVVVVVVVVVVVVVVMQU1FMy4xMDBVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
    "VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
    "VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
    "VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVU="
)
TINY_MP3 = base64.b64decode(TINY_MP3_B64)


def common_manifest(profile: str, source_path: str, mime_type: str, checksum: str) -> dict:
    return {
        "schema_version": 1,
        "profile": profile,
        "asset_id": "sample-asset",
        "content_id": "post:sample",
        "source_class": "project_owned",
        "project": "test",
        "source_repository": "example/assets",
        "source_path": source_path,
        "mime_type": mime_type,
        "sha256": checksum,
        "role": "narration" if profile == "audio" else "presentation_companion",
        "alt": "Sample asset.",
        "caption": "Sample caption.",
        "semantic_description": "Sample governed asset.",
        "claims": ["One bounded claim."],
        "boundaries": ["Not production evidence."],
        "creation_method": "test fixture",
        "contributor": "test",
        "license": "CC0-1.0",
        "public_safe": True,
        "guide_eligible": False,
        "external_resources": False,
        "scripts": False,
    }


def audio_manifest(checksum: str, source_hash: str) -> dict:
    data = common_manifest("audio", "posts/sample/narration.mp3", "audio/mpeg", checksum)
    data.update(
        {
            "duration_ms": 120,
            "codec": "mp3",
            "container": "mp3",
            "source_projection_contract": "dosevai-narration-v1",
            "source_projection_path": "posts/sample/narration.source.txt",
            "source_content_hash": source_hash,
            "coverage_mode": "prose_only",
            "provider_profile": "openai-audio-v1",
            "provider": "openai",
            "provider_route": "audio.speech",
            "model": "gpt-audio-1.5",
            "voice": "cedar",
            "instructions": "Read clearly.",
            "assembly_plan_hash": "sha256:" + "a" * 64,
            "rights_policy": "public-rights-v1",
            "safety_policy": "public-safety-v1",
            "audio_generation_identity": "sha256:" + "0" * 64,
            "disclosure": "AI-generated narration from the public article text.",
            "production_date": "2026-09-20",
        }
    )
    data["audio_generation_identity"] = compute_audio_generation_identity(data)
    return data


def pptx_manifest(checksum: str) -> dict:
    data = common_manifest(
        "presentation_pptx",
        "posts/sample/deck.pptx",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        checksum,
    )
    data.update(
        {
            "slide_count": 5,
            "template_contract": "dosevai-brand-v1",
            "speaker_notes_policy": "forbid",
            "source_format": "governed-public-presentation",
            "render_inspected": True,
            "render_evidence": "owner rendered and inspected",
            "private_notes_removed": True,
        }
    )
    return data


def pdf_manifest(checksum: str) -> dict:
    data = common_manifest("document_pdf", "posts/sample/deck.pdf", "application/pdf", checksum)
    data.update(
        {
            "asset_id": "deck-pdf",
            "role": "document_companion",
            "page_count": 5,
            "source_format": "governed-public-presentation",
            "render_inspected": True,
            "render_evidence": "owner rendered and inspected",
            "private_notes_removed": True,
            "embedded_object_policy": "forbid",
            "annotation_policy": "forbid",
        }
    )
    return data


class AudioPptxManifestTests(unittest.TestCase):
    def workspace(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        (root / "posts" / "sample").mkdir(parents=True)
        return directory, root

    def test_audio_validates_real_mp3_bytes_and_generation_identity(self) -> None:
        _, root = self.workspace()
        package = root / "posts" / "sample"
        asset = package / "narration.mp3"
        sidecar = package / "narration.source.txt"
        asset.write_bytes(TINY_MP3)
        sidecar.write_text("Public narration source.", encoding="utf-8")
        data = audio_manifest(
            hashlib.sha256(TINY_MP3).hexdigest(),
            hashlib.sha256(sidecar.read_bytes()).hexdigest(),
        )
        validated = validate_manifest(data, asset)
        self.assertEqual(validated["profile"], "audio")

    def test_audio_rejects_malformed_mp3(self) -> None:
        _, root = self.workspace()
        asset = root / "posts" / "sample" / "narration.mp3"
        payload = b"not an mp3"
        asset.write_bytes(payload)
        data = audio_manifest(hashlib.sha256(payload).hexdigest(), "b" * 64)
        with self.assertRaises(ManifestError) as caught:
            validate_manifest(data, asset)
        self.assertEqual(caught.exception.code, "AUDIO_DECODE_FAILED")

    def test_audio_generation_identity_binds_recipe_inputs(self) -> None:
        data = audio_manifest("0" * 64, "b" * 64)
        data["voice"] = "marin"
        with self.assertRaises(ManifestError) as caught:
            validate_manifest(data)
        self.assertEqual(caught.exception.code, "AUDIO_GENERATION_IDENTITY_MISMATCH")

    def test_audio_instructions_use_exact_v1_boundary_trim_set(self) -> None:
        data = audio_manifest("0" * 64, "b" * 64)
        data["instructions"] = " Read clearly. "
        data["audio_generation_identity"] = compute_audio_generation_identity(data)
        with self.assertRaises(ManifestError) as caught:
            validate_manifest(data)
        self.assertEqual(caught.exception.code, "AUDIO_INSTRUCTIONS_NOT_CANONICAL")
        data["instructions"] = "\u00a0Read clearly.\u00a0"
        data["audio_generation_identity"] = compute_audio_generation_identity(data)
        self.assertEqual(validate_manifest(data)["instructions"], "\u00a0Read clearly.\u00a0")

    def test_audio_legacy_mapping_is_map_or_reject(self) -> None:
        mapped = map_audio_legacy(
            {
                "slug": "post:sample",
                "source_hash": "b" * 64,
                "url": "https://example.invalid/narration.mp3",
                "model": "gpt-audio-1.5",
                "voice": "cedar",
                "format": "mp3",
                "duration_seconds": "0.120",
                "generated_at": "2026-09-20T00:30:00+02:00",
                "disclosure": "AI narration",
            }
        )
        self.assertEqual(mapped["content_id"], "post:sample")
        self.assertEqual(mapped["duration_ms"], 120)
        self.assertEqual(mapped["production_date"], "2026-09-19")
        with self.assertRaises(ManifestError):
            map_audio_legacy({**{
                "slug": "post:sample", "source_hash": "b" * 64, "model": "x", "voice": "x",
                "format": "wav", "duration_seconds": 1, "generated_at": "2026-09-20",
                "disclosure": "x",
            }})

    def test_audio_repository_audit_binds_public_source_sidecar(self) -> None:
        _, root = self.workspace()
        package = root / "posts" / "sample"
        asset = package / "narration.mp3"
        sidecar = package / "narration.source.txt"
        asset.write_bytes(TINY_MP3)
        sidecar.write_text("Public narration source.", encoding="utf-8")
        data = audio_manifest(
            hashlib.sha256(TINY_MP3).hexdigest(),
            hashlib.sha256(sidecar.read_bytes()).hexdigest(),
        )
        (package / "narration.manifest.yaml").write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        report = audit_repository(root)
        self.assertTrue(report["ok"], report)
        sidecar.write_text("changed", encoding="utf-8")
        report = audit_repository(root)
        self.assertFalse(report["ok"])
        audio_item = next(item for item in report["items"] if item.get("profile") == "audio")
        self.assertEqual(audio_item["code"], "AUDIO_SOURCE_HASH_MISMATCH")

    def test_pptx_is_owner_attested_envelope_only(self) -> None:
        _, root = self.workspace()
        package = root / "posts" / "sample"
        asset = package / "deck.pptx"
        payload = b"not OOXML; owner-attested content is intentionally not parsed"
        asset.write_bytes(payload)
        data = pptx_manifest(hashlib.sha256(payload).hexdigest())
        validated = validate_manifest(data, asset)
        self.assertEqual(validated["slide_count"], 5)

    def test_pptx_derived_pdf_linkage_is_repository_verified(self) -> None:
        _, root = self.workspace()
        package = root / "posts" / "sample"
        pptx_bytes = b"owner-attested-pptx"
        pdf_bytes = b"owner-attested-pdf"
        (package / "deck.pptx").write_bytes(pptx_bytes)
        (package / "deck.pdf").write_bytes(pdf_bytes)
        pdf = pdf_manifest(hashlib.sha256(pdf_bytes).hexdigest())
        (package / "deck.manifest.yaml").write_text(yaml.safe_dump(pdf, sort_keys=False), encoding="utf-8")

        # A PPTX and PDF sharing a stem cannot share one adjacent manifest, so use a distinct PPTX package stem.
        (package / "presentation.pptx").write_bytes(pptx_bytes)
        pptx = pptx_manifest(hashlib.sha256(pptx_bytes).hexdigest())
        pptx["source_path"] = "posts/sample/presentation.pptx"
        pptx["derived_pdf_manifest_path"] = "posts/sample/deck.manifest.yaml"
        pptx["derived_pdf_asset_id"] = "deck-pdf"
        pptx["derived_pdf_sha256"] = hashlib.sha256(pdf_bytes).hexdigest()
        (package / "presentation.manifest.yaml").write_text(yaml.safe_dump(pptx, sort_keys=False), encoding="utf-8")
        report = audit_repository(root)
        self.assertTrue(report["ok"], report)

        pptx["derived_pdf_sha256"] = "f" * 64
        (package / "presentation.manifest.yaml").write_text(yaml.safe_dump(pptx, sort_keys=False), encoding="utf-8")
        report = audit_repository(root)
        self.assertFalse(report["ok"])
        item = next(item for item in report["items"] if item.get("profile") == "presentation_pptx")
        self.assertEqual(item["code"], "PPTX_DERIVED_PDF_SHA256_MISMATCH")


if __name__ == "__main__":
    unittest.main()
