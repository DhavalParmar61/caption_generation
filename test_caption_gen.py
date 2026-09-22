import os
import sys
import json
import unittest
from unittest.mock import patch, mock_open

# Add current directory to path to import caption_gen
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import caption_gen


class TestCaptionGenerator(unittest.TestCase):
    
    def test_parse_captions_standard(self):
        """Test parsing of standard response format."""
        mock_response = (
            "---INSTAGRAM---\n"
            "This is an Instagram caption! #insta\n\n"
            "---FACEBOOK---\n"
            "This is a Facebook caption! #fb\n\n"
            "---LINKEDIN---\n"
            "This is a LinkedIn caption! #li\n\n"
            "---X / TWITTER---\n"
            "Short and punchy! #tech\n\n"
            "---YOUTUBE---\n"
            "Check out this video! #youtube"
        )
        
        parsed = caption_gen.parse_captions(mock_response)
        
        self.assertEqual(parsed["instagram"], "This is an Instagram caption! #insta")
        self.assertEqual(parsed["facebook"], "This is a Facebook caption! #fb")
        self.assertEqual(parsed["linkedin"], "This is a LinkedIn caption! #li")
        self.assertEqual(parsed["twitter"], "Short and punchy! #tech")
        self.assertEqual(parsed["youtube"], "Check out this video! #youtube")

    def test_parse_captions_fallback(self):
        """Test parsing when formatting headers have slight differences (e.g. bolded or lowercase)."""
        mock_response = (
            "### Instagram\n"
            "Insta caption here #insta\n\n"
            "### Facebook\n"
            "FB caption here #fb\n\n"
            "### LinkedIn\n"
            "LI caption here #li\n\n"
            "### X / Twitter\n"
            "Punchy line #punchy\n\n"
            "### YouTube\n"
            "Video description #video"
        )
        
        parsed = caption_gen.parse_captions(mock_response)
        
        self.assertEqual(parsed["instagram"], "Insta caption here #insta")
        self.assertEqual(parsed["facebook"], "FB caption here #fb")
        self.assertEqual(parsed["linkedin"], "LI caption here #li")
        self.assertEqual(parsed["twitter"], "Punchy line #punchy")
        self.assertEqual(parsed["youtube"], "Video description #video")

    def test_load_config_defaults(self):
        """Test config loader returns defaults if file not found."""
        with patch('os.path.exists', return_value=False):
            config = caption_gen.load_config("nonexistent_config.json")
            self.assertEqual(config["provider"], "gemini")
            self.assertEqual(config["temperature"], 0.7)
            self.assertEqual(config["models"]["openai"], "gpt-4o-mini")

    def test_load_config_custom(self):
        """Test config loader parses JSON correctly."""
        mock_json = '{"provider": "openai", "temperature": 0.5, "models": {"openai": "gpt-4-turbo"}}'
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=mock_json)):
                config = caption_gen.load_config("config.json")
                self.assertEqual(config["provider"], "openai")
                self.assertEqual(config["temperature"], 0.5)
                # Should preserve other defaults
                self.assertEqual(config["models"]["gemini"], "gemini-1.5-flash")
                self.assertEqual(config["models"]["openai"], "gpt-4-turbo")

    @patch('json.dump')
    @patch('builtins.open')
    @patch('os.path.exists', return_value=False)
    def test_save_to_history(self, mock_exists, mock_file, mock_json_dump):
        """Test that history log structures details correctly and writes JSON."""
        captions = {
            "instagram": "Insta",
            "facebook": "FB",
            "linkedin": "LI",
            "twitter": "X",
            "youtube": "YT"
        }
        
        success = caption_gen.save_to_history(
            history_path="mock_history.json",
            description="Premium Mug",
            keywords=["coffee", "office"],
            provider="gemini",
            model_name="gemini-1.5-flash",
            captions=captions
        )
        
        self.assertTrue(success)
        mock_file.assert_called_once_with("mock_history.json", "w", encoding="utf-8")
        
        # Verify JSON dump structure was called
        args, kwargs = mock_json_dump.call_args
        written_data = args[0]
        self.assertEqual(len(written_data), 1)
        self.assertEqual(written_data[0]["description"], "Premium Mug")
        self.assertEqual(written_data[0]["keywords"], ["coffee", "office"])
        self.assertEqual(written_data[0]["captions"]["instagram"], "Insta")


if __name__ == '__main__':
    unittest.main()
