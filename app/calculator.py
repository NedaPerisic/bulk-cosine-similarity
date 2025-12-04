"""
Cosine Similarity Calculator - Production Version
==================================================
Uses Trafilatura for content extraction - the same approach Google/Chrome uses.

Trafilatura is the best-performing open-source library for main content extraction,
used by HuggingFace, IBM, Microsoft Research, Stanford, etc.

It uses the same principles as Google's boilerplate detection:
- Text density (text vs tags ratio)
- Link density
- Block position analysis
- Paragraph structure
"""

import os
import re
import time
import random
from typing import Callable, Optional
import json

import requests
import trafilatura
from google.oauth2 import service_account
from googleapiclient.discovery import build
from sentence_transformers import SentenceTransformer
import numpy as np


# ============================================================
# CONFIGURATION
# ============================================================
MIN_CONTENT_LENGTH = 200
MIN_WORDS = 30
MODEL_NAME = os.getenv("MODEL_NAME", "all-MiniLM-L6-v2")

# Load model once at module level
print(f"📦 Loading model: {MODEL_NAME}...")
_model = SentenceTransformer(MODEL_NAME)
print(f"✅ Model loaded!")


# ============================================================
# GOOGLE SHEETS AUTH
# ============================================================
def get_sheets_service():
    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    
    if not creds_json:
        raise ValueError("GOOGLE_CREDENTIALS_JSON environment variable not set.")
    
    creds_dict = json.loads(creds_json)
    credentials = service_account.Credentials.from_service_account_info(
        creds_dict,
        scopes=['https://www.googleapis.com/auth/spreadsheets']
    )
    
    return build('sheets', 'v4', credentials=credentials)


# ============================================================
# THRESHOLD LABELS
# ============================================================
def get_threshold_label(score: Optional[float]) -> str:
    if score is None:
        return "N/A"
    if score >= 0.6:
        return "🟢 Excellent (0.6+)"
    elif score >= 0.4:
        return "🟡 Good (0.4-0.59)"
    elif score >= 0.3:
        return "🟠 Acceptable (0.3-0.39)"
    else:
        return "🔴 Poor (<0.3)"


# ============================================================
# CONTENT SCRAPER - Using Trafilatura
# ============================================================
class ContentScraper:
    """
    Production-grade content scraper using Trafilatura.
    
    Trafilatura uses the same principles as Google's content extraction:
    - Text density analysis
    - Link density detection
    - DOM structure analysis
    - Boilerplate pattern recognition
    """
    
    USER_AGENTS = [
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    ]
    
    ERROR_PATTERNS = [
        r'access\s*denied', r'403\s*forbidden', r'404\s*not\s*found',
        r'captcha', r'cloudflare', r'just\s*a\s*moment',
        r'checking\s*your\s*browser', r'blocked', r'rate\s*limit'
    ]
    
    def __init__(self):
        self.cache = {}
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'en-US,en;q=0.9',
        })
    
    def _is_error_page(self, text: str) -> bool:
        """Check if content is an error page"""
        if not text:
            return True
        text_lower = text.lower()[:500]
        for pattern in self.ERROR_PATTERNS:
            if re.search(pattern, text_lower, re.I):
                return True
        return False
    
    def _validate_content(self, text: str) -> tuple[bool, str]:
        """Validate extracted content"""
        if not text:
            return False, "Empty content"
        
        if len(text) < MIN_CONTENT_LENGTH:
            return False, f"Too short ({len(text)} chars)"
        
        if len(text.split()) < MIN_WORDS:
            return False, f"Too few words ({len(text.split())})"
        
        if self._is_error_page(text):
            return False, "Error page detected"
        
        return True, "Valid"
    
    def fetch(self, url: str) -> Optional[str]:
        """
        Fetch and extract main content from URL using Trafilatura.
        
        Trafilatura automatically:
        - Removes navigation, headers, footers, sidebars
        - Filters out ads and promotional content
        - Extracts only the main article/page content
        - Handles various HTML structures intelligently
        """
        # Normalize URL
        url = url.strip()
        if not url.startswith(('http://', 'https://')):
            url = f'https://{url}'
        
        # Check cache
        if url in self.cache:
            return self.cache[url]
        
        try:
            # Fetch HTML
            self.session.headers['User-Agent'] = random.choice(self.USER_AGENTS)
            response = self.session.get(url, timeout=20, allow_redirects=True)
            response.raise_for_status()
            
            html = response.text
            
            # Extract content using Trafilatura
            # This is the key difference - Trafilatura uses Google-like algorithms:
            # - Text density analysis
            # - Link density detection  
            # - DOM structure parsing
            # - Boilerplate pattern matching
            text = trafilatura.extract(
                html,
                include_comments=False,      # Exclude comments
                include_tables=False,        # Exclude tables (often boilerplate)
                no_fallback=False,           # Use fallback extraction if needed
                favor_precision=True,        # Prefer precision over recall
                deduplicate=True,            # Remove duplicate content
            )
            
            # Validate
            is_valid, reason = self._validate_content(text)
            
            if is_valid:
                self.cache[url] = text
                print(f"    ✅ Extracted {len(text)} chars, {len(text.split())} words")
                return text
            else:
                print(f"    ⚠ Invalid: {reason}")
                return None
                
        except Exception as e:
            print(f"    ⚠ Fetch error: {e}")
            return None


# ============================================================
# SIMILARITY CALCULATOR
# ============================================================
class SimilarityCalculator:
    def __init__(self):
        self.model = _model
        self.scraper = ContentScraper()
    
    def calculate(self, url1: str, url2: str) -> Optional[float]:
        content1 = self.scraper.fetch(url1)
        content2 = self.scraper.fetch(url2)
        
        if not content1 or not content2:
            return None
        
        try:
            # Encode both texts
            emb1 = self.model.encode([content1], normalize_embeddings=True)[0]
            emb2 = self.model.encode([content2], normalize_embeddings=True)[0]
            
            # Cosine similarity (dot product of normalized vectors)
            similarity = float(np.dot(emb1, emb2))
            return round(np.clip(similarity, -1.0, 1.0), 4)
            
        except Exception as e:
            print(f"    ⚠ Embedding error: {e}")
            return None


# ============================================================
# MAIN SERVICE
# ============================================================
class CosineCalculatorService:
    
    @staticmethod
    def col_letter_to_index(letter: str) -> int:
        result = 0
        for char in letter.upper():
            result = result * 26 + (ord(char) - ord('A') + 1)
        return result - 1
    
    @staticmethod
    def col_index_to_letter(index: int) -> str:
        result = ""
        index += 1
        while index > 0:
            index, remainder = divmod(index - 1, 26)
            result = chr(65 + remainder) + result
        return result
    
    @staticmethod
    def process_spreadsheet(
        spreadsheet_id: str,
        sheet_name: str,
        article_col: str,
        target_col: str,
        output_col: str,
        threshold_col: Optional[str],
        progress_callback: Callable[[dict], None]
    ) -> dict:
        
        service = get_sheets_service()
        calculator = SimilarityCalculator()
        
        article_idx = CosineCalculatorService.col_letter_to_index(article_col)
        target_idx = CosineCalculatorService.col_letter_to_index(target_col)
        output_idx = CosineCalculatorService.col_letter_to_index(output_col)
        
        if threshold_col:
            threshold_idx = CosineCalculatorService.col_letter_to_index(threshold_col)
        else:
            threshold_idx = output_idx + 1
        
        threshold_letter = CosineCalculatorService.col_index_to_letter(threshold_idx)
        
        progress_callback({
            "stage": "reading_spreadsheet",
            "message": f"Reading {sheet_name}..."
        })
        
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"'{sheet_name}'!A2:Z"
        ).execute()
        
        rows = result.get('values', [])
        if not rows:
            return {"status": "empty", "message": "No data found", "processed": 0}
        
        rows_to_process = []
        for i, row in enumerate(rows, start=2):
            article_url = row[article_idx] if len(row) > article_idx else None
            target_url = row[target_idx] if len(row) > target_idx else None
            existing = row[output_idx] if len(row) > output_idx else None
            
            if not article_url or not target_url:
                continue
            if existing and str(existing).strip() not in ['', 'N/A', '0', 'ERROR']:
                continue
            
            rows_to_process.append((i, article_url.strip(), target_url.strip()))
        
        total = len(rows_to_process)
        if total == 0:
            return {"status": "complete", "message": "All rows already processed", "processed": 0}
        
        progress_callback({
            "stage": "processing",
            "total": total,
            "current": 0,
            "message": f"Processing {total} rows..."
        })
        
        updates = []
        success = 0
        failed = 0
        
        for idx, (row_num, article_url, target_url) in enumerate(rows_to_process):
            print(f"\n[{idx+1}/{total}] Row {row_num}")
            print(f"  Article: {article_url[:50]}...")
            print(f"  Target: {target_url[:50]}...")
            
            progress_callback({
                "stage": "processing",
                "total": total,
                "current": idx + 1,
                "row": row_num,
                "message": f"Processing row {row_num} ({idx+1}/{total})"
            })
            
            similarity = calculator.calculate(article_url, target_url)
            
            if similarity is not None:
                label = get_threshold_label(similarity)
                print(f"  ✅ Score: {similarity} - {label}")
                
                updates.append({
                    'range': f"'{sheet_name}'!{output_col}{row_num}",
                    'values': [[f"{similarity:.4f}"]]
                })
                updates.append({
                    'range': f"'{sheet_name}'!{threshold_letter}{row_num}",
                    'values': [[label]]
                })
                success += 1
            else:
                print(f"  ❌ Failed")
                updates.append({
                    'range': f"'{sheet_name}'!{output_col}{row_num}",
                    'values': [["N/A"]]
                })
                updates.append({
                    'range': f"'{sheet_name}'!{threshold_letter}{row_num}",
                    'values': [["N/A"]]
                })
                failed += 1
            
            if len(updates) >= 10:
                service.spreadsheets().values().batchUpdate(
                    spreadsheetId=spreadsheet_id,
                    body={'valueInputOption': 'USER_ENTERED', 'data': updates}
                ).execute()
                updates = []
            
            time.sleep(random.uniform(0.5, 1.5))
        
        if updates:
            service.spreadsheets().values().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={'valueInputOption': 'USER_ENTERED', 'data': updates}
            ).execute()
        
        return {
            "status": "complete",
            "processed": total,
            "success": success,
            "failed": failed,
            "sheet": sheet_name
        }
