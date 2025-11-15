"""Tests for JSON file I/O tools."""
import json
import tempfile
from pathlib import Path

import pytest

from resume_builder.tools.json_file_io import ReadJsonFileTool, WriteJsonFileTool


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def read_tool():
    """Create a ReadJsonFileTool instance."""
    return ReadJsonFileTool()


@pytest.fixture
def write_tool():
    """Create a WriteJsonFileTool instance."""
    return WriteJsonFileTool()


class TestReadJsonFileTool:
    """Tests for ReadJsonFileTool."""
    
    def test_read_existing_file(self, read_tool, temp_dir):
        """Test reading an existing valid JSON file."""
        test_file = temp_dir / "test.json"
        test_data = {"status": "success", "message": "Test message", "data": [1, 2, 3]}
        test_file.write_text(json.dumps(test_data), encoding='utf-8')
        
        result = read_tool._run(str(test_file))
        
        assert "✅ JSON file read successfully" in result
        assert "status" in result
        assert "Test message" in result
    
    def test_read_missing_file(self, read_tool, temp_dir):
        """Test reading a missing file returns structured error."""
        missing_file = temp_dir / "missing.json"
        
        result = read_tool._run(str(missing_file))
        
        assert "[error] JSON file not found:" in result
        assert "missing.json" in result
    
    def test_read_empty_file(self, read_tool, temp_dir):
        """Test reading an empty file returns structured error."""
        empty_file = temp_dir / "empty.json"
        empty_file.write_text("", encoding='utf-8')
        
        result = read_tool._run(str(empty_file))
        
        assert "[error] JSON file is empty:" in result
    
    def test_read_invalid_json(self, read_tool, temp_dir):
        """Test reading invalid JSON returns structured error."""
        invalid_file = temp_dir / "invalid.json"
        invalid_file.write_text("{ invalid json }", encoding='utf-8')
        
        result = read_tool._run(str(invalid_file))
        
        assert "[error] Failed to parse JSON file" in result
    
    def test_read_cached_file(self, read_tool, temp_dir):
        """Test that files are cached and subsequent reads use cache."""
        test_file = temp_dir / "cache_test.json"
        test_data = {"status": "success", "message": "Cached"}
        test_file.write_text(json.dumps(test_data), encoding='utf-8')
        
        # First read
        result1 = read_tool._run(str(test_file))
        assert "✅ JSON file read successfully" in result1
        
        # Second read should use cache
        result2 = read_tool._run(str(test_file))
        assert "cached" in result2.lower()


class TestWriteJsonFileTool:
    """Tests for WriteJsonFileTool."""
    
    def test_write_valid_json(self, write_tool, temp_dir):
        """Test writing valid JSON data."""
        test_file = temp_dir / "write_test.json"
        test_data = {"status": "success", "message": "Written successfully"}
        
        result = write_tool._run(str(test_file), json.dumps(test_data))
        
        assert "✅ JSON file written successfully" in result
        assert test_file.exists()
        
        # Verify content
        written_data = json.loads(test_file.read_text(encoding='utf-8'))
        assert written_data == test_data
    
    def test_write_invalid_json(self, write_tool, temp_dir):
        """Test writing invalid JSON returns error."""
        test_file = temp_dir / "invalid_write.json"
        invalid_json = "{ invalid json }"
        
        result = write_tool._run(str(test_file), invalid_json)
        
        assert "[error] Invalid JSON data:" in result
        assert not test_file.exists()
    
    def test_write_empty_data(self, write_tool, temp_dir):
        """Test writing empty data returns error."""
        test_file = temp_dir / "empty_write.json"
        
        result = write_tool._run(str(test_file), "")
        
        assert "[error]" in result
        assert "empty" in result.lower()
    
    def test_write_non_dict(self, write_tool, temp_dir):
        """Test writing non-dict JSON returns error."""
        test_file = temp_dir / "array_write.json"
        array_json = json.dumps([1, 2, 3])
        
        result = write_tool._run(str(test_file), array_json)
        
        assert "[error] JSON data must be an object (dict)" in result
    
    def test_atomic_write(self, write_tool, temp_dir):
        """Test that writes are atomic (temp file then rename)."""
        test_file = temp_dir / "atomic_test.json"
        test_data = {"status": "success", "message": "Atomic write"}
        
        result = write_tool._run(str(test_file), json.dumps(test_data))
        
        assert "✅ JSON file written successfully" in result
        # Temp file should not exist after successful write
        temp_file = test_file.with_suffix(test_file.suffix + '.tmp')
        assert not temp_file.exists()
        assert test_file.exists()
    
    def test_creates_parent_directories(self, write_tool, temp_dir):
        """Test that parent directories are created if they don't exist."""
        nested_file = temp_dir / "nested" / "deep" / "file.json"
        test_data = {"status": "success"}
        
        result = write_tool._run(str(nested_file), json.dumps(test_data))
        
        assert "✅ JSON file written successfully" in result
        assert nested_file.exists()
        assert nested_file.parent.exists()

