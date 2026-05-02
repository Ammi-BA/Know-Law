import os
import pytest
import pandas as pd
import tempfile
import importlib.util

# Dynamically import the module because of parentheses in the filename
MODULE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'brain_AI_databese(vector).py'))
spec = importlib.util.spec_from_file_location("brain_ai", MODULE_PATH)
brain_ai = importlib.util.module_from_spec(spec)
spec.loader.exec_module(brain_ai)

@pytest.fixture
def temp_csv_dir():
    """Fixture to create a temporary directory for CSV files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir

def test_load_all_csvs_happy_path(temp_csv_dir):
    """
    HAPPY PATH: Test loading a valid CSV file with 'text' and 'source' columns.
    Ensures the RAG system can correctly parse legal documents.
    """
    # Arrange
    csv_path = os.path.join(temp_csv_dir, "valid_law.csv")
    df_mock = pd.DataFrame({"text": ["Article 1: Law applies here."], "source": ["Penal Code"]})
    df_mock.to_csv(csv_path, index=False)

    # Act
    df_result = brain_ai.load_all_csvs(temp_csv_dir)

    # Assert
    assert not df_result.empty, "DataFrame should not be empty on Happy Path."
    assert "text" in df_result.columns, "Text column missing."
    assert df_result.iloc[0]["text"] == "Article 1: Law applies here.", "Text content mismatch."
    assert df_result.iloc[0]["law_file"] == "valid_law.csv", "Law file metadata missing."

def test_load_all_csvs_edge_case_empty(temp_csv_dir):
    """
    EDGE CASE: Test loading an empty folder.
    Ensures the system does not crash when no datasets are present, returning an empty DataFrame.
    """
    # Act
    df_result = brain_ai.load_all_csvs(temp_csv_dir)

    # Assert
    assert df_result.empty, "DataFrame should be empty when no CSVs are present."
    # Important Phase 3 Checklist: No crashes or unhandled exceptions occurred.

def test_load_all_csvs_negative_bad_columns(temp_csv_dir):
    """
    NEGATIVE TEST: Test loading a CSV with completely wrong data (no text/content column).
    Ensures the system skips invalid files without throwing an unhandled exception.
    """
    # Arrange
    csv_path = os.path.join(temp_csv_dir, "bad_data.csv")
    df_mock = pd.DataFrame({"random_col": [1, 2, 3], "another_col": ["a", "b", "c"]})
    df_mock.to_csv(csv_path, index=False)

    # Act
    df_result = brain_ai.load_all_csvs(temp_csv_dir)

    # Assert
    # The function should skip files without 'text', 'content', or 'مادة'.
    assert df_result.empty, "DataFrame should be empty because the invalid CSV was safely skipped."
