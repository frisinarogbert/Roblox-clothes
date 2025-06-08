import requests
import os
import re
import argparse
import time
import string
import random
import json
from rich.console import Console
from PIL import Image

console = Console(highlight=False)

def cprint(color, content):
    console.print(f"[bold {color}]{content}[/bold {color}]")

def load_settings():
    try:
        if os.path.exists('settings.json'):
            with open('settings.json', 'r') as f:
                return json.load(f)
    except Exception as e:
        cprint('yellow', f"Error loading settings: {e}")
    return {}

def save_settings(settings):
    try:
        with open('settings.json', 'w') as f:
            json.dump(settings, f, indent=4)
        cprint('green', "Settings saved successfully!")
    except Exception as e:
        cprint('red', f"Error saving settings: {e}")

def get_asset_id(cookie, clothing_id):
    for attempt in range(3):
        try:
            response = requests.get(
                f'https://assetdelivery.roblox.com/v1/assetId/{clothing_id}',
                cookies={".ROBLOSECURITY": cookie},
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Referer': 'https://www.roblox.com/',
                    'Origin': 'https://www.roblox.com'
                },
                timeout=10 # Adding a timeout
            )
            response.raise_for_status()
            data = response.json()
            if data.get("IsCopyrightProtected"):
                cprint('red', f"Copyright Protected! ID: {clothing_id}")
                return "ERROR_COPYRIGHT_PROTECTED"
            location = data.get('location')
            if location:
                # This subsequent request might also need retries/timeout, but per instructions, focusing on the main ones.
                asset_id_response = requests.get(location, timeout=10)
                asset_id_response.raise_for_status()
                asset_id_content = str(asset_id_response.content)
                # Using regex for safer parsing
                match = re.search(r'<url>http://www.roblox.com/asset/\?id=(\d+)</url>', asset_id_content)
                if match:
                    return match.group(1)
                else:
                    cprint('red', f"Could not parse asset ID from location response for {clothing_id}")
                    return None # Or handle as a retryable error if appropriate
            return None # No location found
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            cprint('yellow', f"Attempt {attempt + 1} for get_asset_id ({clothing_id}) failed: {e}. Retrying in 2 seconds...")
            if attempt < 2: # Don't sleep on the last attempt
                time.sleep(2)
            else:
                cprint('red', f"Max retries reached for get_asset_id ({clothing_id}). Error: {e}")
                return None # Failed after retries
        except requests.RequestException as e: # Catch other request-related errors (like HTTP errors)
            cprint('red', f"Error getting asset ID for {clothing_id}: {e}")
            return None # Failed due to other request error
    return None # Fallback if loop completes without returning

def get_png_url(cookie, asset_id):
    for attempt in range(3):
        try:
            response = requests.get(
                f'https://assetdelivery.roblox.com/v1/assetId/{asset_id}',
                cookies={".ROBLOSECURITY": cookie},
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Referer': 'https://www.roblox.com/',
                    'Origin': 'https://www.roblox.com'
                },
                timeout=10 # Adding a timeout
            )
            response.raise_for_status()
            data = response.json()
            if data.get("IsCopyrightProtected"):
                cprint('red', f"Copyright Protected! ID: {asset_id}")
                return "ERROR_COPYRIGHT_PROTECTED" # Specific return for copyright
            png_url = data.get('location')
            if png_url:
                # This subsequent request might also benefit from retries, but applying to primary request first
                png_response = requests.get(png_url, timeout=10)
                png_response.raise_for_status() # Ensure download itself is checked
                return png_response.content
            else:
                cprint('red', f"No location found for PNG URL for asset ID: {asset_id}")
                return None
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            cprint('yellow', f"Attempt {attempt + 1} for get_png_url ({asset_id}) failed: {e}. Retrying in 2 seconds...")
            if attempt < 2: # Don't sleep on the last attempt
                time.sleep(2)
            else:
                cprint('red', f"Max retries reached for get_png_url ({asset_id}). Error: {e}")
                return None # Failed after retries
        except requests.RequestException as e: # Catch other request-related errors
            cprint('red', f"Error getting PNG URL for {asset_id}: {e}")
            return None # Failed due to other request error
    return None # Fallback if loop completes

def get_thumbnail(asset_id):
    for attempt in range(3):
        try:
            response = requests.post(
                "https://thumbnails.roblox.com/v1/batch",
                json=[{
                    "format": "png",
                    "requestId": f"{asset_id}::Asset:420x420:png:regular",
                    "size": "420x420",
                    "targetId": asset_id,
                    "token": "",
                    "type": "Asset"
                }],
                timeout=10 # Adding a timeout
            )
            response.raise_for_status()
            data = response.json()
            if data and data.get("data") and len(data["data"]) > 0 and data["data"][0].get("imageUrl"):
                thumbnail_url = data["data"][0]["imageUrl"]
                # This subsequent request might also benefit from retries
                thumb_response = requests.get(thumbnail_url, timeout=10)
                thumb_response.raise_for_status()
                return thumb_response.content
            else:
                cprint('red', f"Could not extract thumbnail URL from response for {asset_id}. Response: {data}")
                return None
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            cprint('yellow', f"Attempt {attempt + 1} for get_thumbnail ({asset_id}) failed: {e}. Retrying in 2 seconds...")
            if attempt < 2: # Don't sleep on the last attempt
                time.sleep(2)
            else:
                cprint('red', f"Max retries reached for get_thumbnail ({asset_id}). Error: {e}")
                return None # Failed after retries
        except requests.RequestException as e: # Catch other request-related errors
            cprint('red', f"Error getting thumbnail for {asset_id}: {e}")
            return None # Failed due to other request error
    return None # Fallback if loop completes

def download_clothing_image(cookie, clothing_id, asset_type="shirts"):
    try:
        # Create necessary directories
        for dir_path in ['clothes', f'clothes/{asset_type}']:
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)

        # Validate clothing_id format
        if not clothing_id.isdigit():
            cprint('red', f"Invalid clothing ID format: '{clothing_id}'. ID must consist of digits only.")
            return False

        # Get asset ID
        asset_id = get_asset_id(cookie, clothing_id) # Handles its own retries and error printing
        if not asset_id:
            # get_asset_id already printed the specific error (network, max retries, etc.)
            return False
        if asset_id == "ERROR_COPYRIGHT_PROTECTED":
            # Message was already printed by get_asset_id
            return False

        # Get PNG content
        # Note: asset_id here is the processed one from get_asset_id
        png_content = get_png_url(cookie, asset_id) # Handles its own retries and error printing
        if not png_content:
            # get_png_url already printed the specific error
            return False
        if png_content == "ERROR_COPYRIGHT_PROTECTED":
            # Message was already printed by get_png_url
            return False

        # Save the image
        # Use original clothing_id for filename consistency, add a small random suffix to prevent potential collisions
        random_suffix = ''.join(random.choices(string.ascii_letters + string.digits, k=4))
        file_name = f'clothes/{asset_type}/{clothing_id}_{random_suffix}.png'
        with open(file_name, 'wb') as f:
            f.write(png_content)

        cprint('green', f'Successfully downloaded {file_name}')
        return file_name

    except Exception as e: # Catch any other unexpected errors during the download process
        cprint('red', f"An unexpected error occurred in download_clothing_image for ID {clothing_id}: {e}")
        return False

def main():
    # Load saved settings

        # Get PNG content
        png_content = get_png_url(cookie, asset_id)
        if not png_content:
            cprint('red', "Failed to download PNG")
            return False

        # Save the image
        file_name = f'clothes/{asset_type}/{clothing_id}_{random.randint(0, 100)}.png'
        with open(file_name, 'wb') as f:
            f.write(png_content)
        
        cprint('green', f'Successfully downloaded {file_name}')
        return file_name

    except Exception as e:
        cprint('red', f"Error downloading clothing: {e}")
        return False

def main():
    # Load saved settings
    settings = load_settings()
    
    # Set up command-line argument parsing
    parser = argparse.ArgumentParser(description='Download Roblox shirts by ID or from a file containing IDs.')
    parser.add_argument('file', nargs='?', help='Optional: File containing clothing IDs or a single clothing ID')
    parser.add_argument('--cookie', help='ROBLOSECURITY cookie for authentication')
    parser.add_argument('--save-cookie', action='store_true', help='Save the provided cookie to settings')
    parser.add_argument('--clear-settings', action='store_true', help='Clear saved settings')
    args = parser.parse_args()

    # Handle clear settings
    if args.clear_settings:
        if os.path.exists('settings.json'):
            os.remove('settings.json')
            cprint('green', "Settings cleared successfully!")
        return

    # Get cookie from argument, settings, or prompt
    cookie = args.cookie
    if not cookie and 'cookie' in settings:
        cookie = settings['cookie']
    
    if not cookie:
        cookie = input('Enter your ROBLOSECURITY cookie: ')
        if input('Would you like to save this cookie for future use? (y/n): ').lower() == 'y':
            settings['cookie'] = cookie
            save_settings(settings)

    # Save cookie if requested
    if args.save_cookie and args.cookie:
        settings['cookie'] = args.cookie
        save_settings(settings)

    if args.file:
        # Check if the argument is a clothing ID
        if args.file.isdigit():
            clothing_id = args.file
            download_clothing_image(cookie, clothing_id)
        else:
            with open(args.file, 'r') as file:
                lines = file.readlines()
            
            os.system("cls")
            
            for line in lines:
                if line.startswith('https://www.roblox.com/catalog/'):
                    match = re.search(r'/(\d+)/', line)
                    if match:
                        clothing_id = match.group(1)
                    else:
                        cprint('red', f'Failed to extract clothing ID from URL: {line}')
                        continue
                else:
                    clothing_id = line.strip()

                download_clothing_image(cookie, clothing_id)
    else:
        clothing_id = input('Enter the clothing ID or URL: ')
        if clothing_id.startswith('https://www.roblox.com/catalog/'):
            match = re.search(r'/(\d+)/', clothing_id)
            if match:
                clothing_id = match.group(1)
            else:
                cprint('red', 'Failed to extract clothing ID from the provided URL.')
                return
        
        download_clothing_image(cookie, clothing_id)

    cprint('cyan', 'Finished downloading clothing items.')

if __name__ == "__main__":
    main() 