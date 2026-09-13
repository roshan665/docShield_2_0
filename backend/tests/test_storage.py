"""Tests for StorageService abstraction."""



def test_mock_storage_operations(mock_storage):
    """Verifies storage upload, download, exists, and delete abstractions."""
    test_data = b"Digital Forensic Evidence Memory Dump Test Bytes"
    key = "cases/case-123/evidence-456.raw"
    bucket = "sih190-evidence"

    # Upload
    uploaded_key = mock_storage.upload(test_data, key=key, bucket=bucket, content_type="application/octet-stream")
    assert uploaded_key == key

    # Exists
    assert mock_storage.exists(key, bucket) is True
    assert mock_storage.exists("non-existent-key", bucket) is False

    # Download
    downloaded = mock_storage.download(key, bucket)
    assert downloaded == test_data

    # Delete
    assert mock_storage.delete(key, bucket) is True
    assert mock_storage.exists(key, bucket) is False
