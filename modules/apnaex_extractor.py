import asyncio
import base64
import json
import re
from base64 import b64decode
import aiohttp
import cloudscraper
from bs4 import BeautifulSoup
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from logger import LOGGER

# Hardcoded keys from ApnaEx/appex_v4.py
AES_KEY = b'638udh3829162018'
AES_IV = b'fedcba9876543210'

def decrypt(enc):
    """Decrypts AES-encrypted strings from Appx API."""
    try:
        if not enc:
            return ""
        enc = b64decode(enc.split(':')[0])
        if len(enc) == 0:
            return ""
        cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
        plaintext = unpad(cipher.decrypt(enc), AES.block_size)
        return plaintext.decode('utf-8')
    except Exception as e:
        LOGGER.error(f"Decryption error: {e}")
        return ""

def decode_base64(encoded_str):
    try:
        decoded_bytes = base64.b64decode(encoded_str)
        return decoded_bytes.decode('utf-8')
    except Exception as e:
        return str(e)

async def fetch(session, url, headers):
    """Async fetch helper."""
    try:
        async with session.get(url, headers=headers) as response:
            content = await response.text()
            if response.status != 200:
                LOGGER.error(f"Error fetching {url}: {response.status} | Response: {content[:200]}")
                return {}
            
            # Some responses might be HTML wrapped JSON, handled via soup
            try:
                soup = BeautifulSoup(content, 'html.parser')
                return json.loads(str(soup))
            except json.JSONDecodeError:
                LOGGER.error(f"JSON Decode Error for {url}. Content: {content[:500]}") # Log first 500 chars
                return {}
            except Exception as e:
                 # Try direct load if soup fails
                try:
                    return json.loads(content)
                except:
                     LOGGER.error(f"Failed to parse response from {url}: {e}")
                     return {}

    except Exception as e:
        LOGGER.error(f"Fetch error {url}: {e}")
        return {}
# ... (process_video and handle_course_topic remain same)

async def extract_batch_apnaex_logic(batch_id, api_base, token, userid):
    """
    Main entry point for ApnaEx extraction logic using asyncio.
    
    Args:
        batch_id (str): The course/batch ID.
        api_base (str): Base API URL.
        token (str): Auth token.
        userid (str): User ID (MANDATORY).
        
    Returns:
        list: List of dictionaries containing extracted content.
    """
    
    headers = {
        "Client-Service": "Appx",
        "source": "website",
        "Auth-Key": "appxapi",
        "Authorization": token,
        "User-ID": str(userid),
        "User-Agent": "okhttp/4.9.1"
    }
    
    # Ensure protocol
    if not api_base.startswith("http"):
        api_base = f"https://{api_base}"

    all_data = []
    
    async with aiohttp.ClientSession() as session:
        # Fetch Subjects
        subjects_url = f"{api_base}/get/allsubjectfrmlivecourseclass?courseid={batch_id}&start=-1"
        r1 = await fetch(session, subjects_url, headers)
        
        subjects = r1.get("data", [])
        if not subjects:
            LOGGER.warning(f"No subjects found for batch {batch_id}")
            return []
            
        for subject in subjects:
            si = subject.get("subjectid")
            sn = subject.get("subject_name")
            
            # Fetch Topics for Subject
            topics_url = f"{api_base}/get/alltopicfrmlivecourseclass?courseid={batch_id}&subjectid={si}&start=-1"
            r2 = await fetch(session, topics_url, headers)
            topics = sorted(r2.get("data", []), key=lambda x: x.get("topicid"))
            
            # Process Topics concurrently
            topic_tasks = [
                handle_course_topic(session, api_base, batch_id, si, sn, t, headers)
                for t in topics
            ]
            topic_results = await asyncio.gather(*topic_tasks)
            
            # Aggregate data
            for res in topic_results:
                if res:
                    all_data.extend(res)
                    
    return all_data

async def handle_course_topic(session, api_base, batch_id, subject_id, subject_name, topic, headers):
    """Handle topic extraction with better Appx compatibility"""
    try:
        topic_id = topic.get("topicid") or topic.get("_id") or topic.get("id")
        topic_name = topic.get("topic_name") or topic.get("name") or "Unknown"

        # Using stable endpoint (not apiv3)
        content_url = f"{api_base}/get/livecourseclassbycoursesubtopconcept?courseid={batch_id}&subjectid={subject_id}&topicid={topic_id}&start=-1"

        data = await fetch(session, content_url, headers)

        items = data.get("data", [])
        results = []

        for item in items:

            name = item.get("Title") or item.get("title") or "file"
            timestamp = item.get("created_at") or item.get("createdAt") or ""

            # ---------------- VIDEO ----------------
            if item.get("material_type") == "VIDEO":

                url = (
                    item.get("video_url")
                    or item.get("download_link")
                    or item.get("url")
                )

                # encrypted links support (Appx v4)
                if not url:
                    enc_links = item.get("encrypted_links", [])
                    for link in enc_links:
                        path = link.get("path")
                        key = link.get("key")

                        if path:
                            try:
                                decrypted_path = decrypt(path)

                                if key:
                                    k1 = decrypt(key)
                                    k2 = decode_base64(k1)
                                    url = f"{decrypted_path}*{k2}"
                                else:
                                    url = decrypted_path
                                break
                            except:
                                pass

                if url:
                    results.append({
                        "url": url,
                        "name": name,
                        "type": "video",
                        "topicName": topic_name,
                        "subjectName": subject_name,
                        "timestamp": timestamp
                    })

            # ---------------- PDF ----------------
            elif item.get("material_type") in ["PDF", "DOCUMENT"]:

                url = (
                    item.get("pdf_link")
                    or item.get("pdfLink")
                    or item.get("url")
                )

                # encrypted pdf support
                if not url:
                    p1 = item.get("pdf_encrypted_link")
                    k1 = item.get("pdf_encryption_key")

                    if p1:
                        try:
                            dp1 = decrypt(p1)

                            if k1:
                                dk1 = decrypt(k1)
                                dk2 = decode_base64(dk1)
                                url = f"{dp1}*{dk2}"
                            else:
                                url = dp1
                        except:
                            pass

                if url:
                    results.append({
                        "url": url,
                        "name": name,
                        "type": "pdf",
                        "topicName": topic_name,
                        "subjectName": subject_name,
                        "timestamp": timestamp
                    })

        return results

    except Exception as e:
        LOGGER.error(f"Topic processing error: {e}")
        return []
