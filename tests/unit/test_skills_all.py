"""Tests for backend.skills modules — catalog, creator, executor, loader, learning_loop."""
import pytest


class TestSkillsCatalog:
    def test_import(self):
        from backend.skills.catalog import SkillCatalog, SkillMeta
        sc = SkillCatalog()
        assert sc is not None


class TestSkillsCreator:
    def test_import(self):
        from backend.skills.creator import SkillCreatorAgent, SkillEvaluatorAgent, SkillPromotionGate
        assert SkillCreatorAgent is not None
        assert SkillEvaluatorAgent is not None
        assert SkillPromotionGate is not None


class TestSkillsExecutor:
    def test_import(self):
        from backend.skills.executor import SkillExecutor, SkillRunResult
        assert SkillExecutor is not None
        assert SkillRunResult is not None


class TestSkillsLoader:
    def test_import(self):
        from backend.skills.loader import SkillLoader, load_skill_roots, validate_skill_format
        assert SkillLoader is not None

    def test_validate_format(self):
        from backend.skills.loader import validate_skill_format
        valid, errors = validate_skill_format({"name": "test", "domain": "recon"}, "body")
        assert isinstance(valid, bool)


class TestSkillsLearningLoop:
    def test_import(self):
        from backend.skills.learning_loop import PerScanLearningLoop, ScanOutcome
        assert PerScanLearningLoop is not None
        assert ScanOutcome is not None
