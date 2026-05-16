import os
import json
import pytest
from unittest.mock import patch, MagicMock
from scripts.longform_script_generator import LongformScriptGenerator, REQUIRED_SECTIONS

# Mock response that contains all sections and valid JSON
MOCK_VALID_RESPONSE = """
[HOOK]
Did you know that oil prices are spiking? And in this video, I'm going to show you exactly why.

[CONTEXT]
The situation before this was calm.

[CONFLICT]
But then everything changed.

[EVIDENCE]
Here are the facts to back it up.

[TWIST]
The part most people don't know is this.

[RESOLUTION]
Going forward, it means a lot.

[CTA]
If you want to understand more, I've already covered that — link is right there.

```json
{
  "title_options": ["Title 1", "Title 2", "Title 3"],
  "thumbnail_keywords": ["oil", "pump", "money"],
  "search_keywords": ["oil prices", "economy"],
  "estimated_duration_minutes": 8
}
```
"""

MOCK_MISSING_SECTION_RESPONSE = """
[HOOK]
Did you know that oil prices are spiking? And in this video, I'm going to show you exactly why.

[CONTEXT]
The situation before this was calm.

[CONFLICT]
But then everything changed.

[EVIDENCE]
Here are the facts to back it up.

[RESOLUTION]
Going forward, it means a lot.

[CTA]
If you want to understand more, I've already covered that — link is right there.

```json
{
  "title_options": ["Title 1", "Title 2", "Title 3"]
}
```
"""

class TestLongformScriptGenerator:
    
    @patch('scripts.longform_script_generator.os.getenv', return_value='dummy_key')
    def setup_method(self, method, mock_getenv):
        self.generator = LongformScriptGenerator(api_key="dummy_key")
        # Prevent actually saving files during tests
        self.generator._save_output = MagicMock()

    def test_parse_valid_response(self):
        result = self.generator._parse_script_response(MOCK_VALID_RESPONSE, "Test Topic")
        
        # Check topic
        assert result["topic"] == "Test Topic"
        
        # Check sections
        assert len(result["sections"]) == 7
        assert result["sections"]["hook"] == "Did you know that oil prices are spiking? And in this video, I'm going to show you exactly why."
        assert result["sections"]["twist"] == "The part most people don't know is this."
        
        # Check metadata
        assert "title_options" in result["metadata"]
        assert len(result["metadata"]["title_options"]) == 3
        
        # Check full_script
        assert "[HOOK]" not in result["full_script"]
        assert "```json" not in result["full_script"]
        assert "Did you know that oil" in result["full_script"]

    def test_parse_missing_section(self):
        with pytest.raises(ValueError) as excinfo:
            self.generator._parse_script_response(MOCK_MISSING_SECTION_RESPONSE, "Test Topic")
        
        assert "Missing required sections" in str(excinfo.value)
        assert "[TWIST]" in str(excinfo.value)

    def test_parse_missing_json(self):
        no_json_response = MOCK_VALID_RESPONSE.replace("```json", "").replace("```", "").replace("{", "").replace("}", "")
        with pytest.raises(ValueError) as excinfo:
            self.generator._parse_script_response(no_json_response, "Test Topic")
            
        assert "Could not find the JSON metadata block" in str(excinfo.value)

