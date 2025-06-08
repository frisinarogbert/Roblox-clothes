import unittest
from unittest.mock import patch, mock_open
import sys
import os

# Add the parent directory to sys.path to allow importing shyt
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Attempt to import functions from shyt.py
# We expect this might be problematic due to the state of shyt.py
try:
    from shyt import get_asset_id, download_clothing_image, cprint
except ImportError as e:
    # If shyt.py itself has syntax errors (e.g. from duplicated main) or other import issues,
    # this will catch it. We'll raise an error to make it clear in the subtask report.
    raise ImportError(f"Could not import from shyt.py, possibly due to its structural issues: {e}")
except SyntaxError as e:
    raise SyntaxError(f"Syntax error while trying to import from shyt.py, likely due to duplicated/malformed main: {e}")


class TestShytCoreLogic(unittest.TestCase):

    @patch('shyt.requests.get')
    def test_get_asset_id_success(self, mock_get):
        # Mock the initial response for assetId
        mock_response_initial = mock_get.return_value
        mock_response_initial.raise_for_status.return_value = None
        mock_response_initial.json.return_value = {
            "IsCopyrightProtected": False,
            "location": "http://www.roblox.com/asset/?id=12345"
        }

        # Mock the second response for the location
        mock_response_location = type(mock_get.return_value)() # Create a new mock object
        mock_response_location.raise_for_status.return_value = None
        mock_response_location.content = b"<xml><url>http://www.roblox.com/asset/?id=67890</url></xml>"

        # Make requests.get return the initial response first, then the location response
        mock_get.side_effect = [mock_response_initial, mock_response_location]

        asset_id = get_asset_id("test_cookie", "123")
        self.assertEqual(asset_id, "67890")
        self.assertEqual(mock_get.call_count, 2)

    @patch('shyt.requests.get')
    def test_get_asset_id_copyright_protected(self, mock_get):
        mock_response = mock_get.return_value
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"IsCopyrightProtected": True}

        result = get_asset_id("test_cookie", "123")
        self.assertEqual(result, "ERROR_COPYRIGHT_PROTECTED")

    @patch('shyt.get_asset_id')
    @patch('shyt.get_png_url')
    @patch('builtins.open', new_callable=mock_open)
    @patch('shyt.os.makedirs')
    @patch('shyt.os.path.exists', return_value=False) # Assume directories don't exist initially
    def test_download_clothing_image_success(self, mock_exists, mock_makedirs, mock_file_open, mock_get_png, mock_get_asset_id):
        mock_get_asset_id.return_value = "67890"
        mock_get_png.return_value = b"fake_image_data"

        result = download_clothing_image("test_cookie", "12345", "shirts")

        self.assertTrue(result.startswith("clothes/shirts/12345_"))
        self.assertTrue(result.endswith(".png"))
        mock_makedirs.assert_any_call('clothes')
        mock_makedirs.assert_any_call('clothes/shirts')
        mock_file_open.assert_called_once_with(result, 'wb')
        handle = mock_file_open()
        handle.write.assert_called_once_with(b"fake_image_data")

    def test_download_clothing_image_invalid_id_format(self):
        # This test relies on cprint, which might be an issue if not imported,
        # but the function should return False before cprint is heavily used for this case.
        result = download_clothing_image("test_cookie", "invalidID", "shirts")
        self.assertFalse(result)

# It's generally not recommended to run tests directly like this if using a test runner,
# but for a simple script, this allows `python tests/test_shyt.py` to work.
# However, the subtask environment will likely use a test runner.
# if __name__ == '__main__':
#    unittest.main()
