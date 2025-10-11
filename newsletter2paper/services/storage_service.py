"""
Storage Service Module
Handles file storage operations using Supabase storage.
"""

import os
import logging
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

logger = logging.getLogger(__name__)

class StorageService:
    def __init__(self):
        """Initialize Supabase client for storage operations."""
        supabase_url = os.environ.get('SUPABASE_URL', '')
        supabase_key = os.environ.get('SUPABASE_KEY', '')
        
        if not supabase_url or not supabase_key:
            raise Exception("SUPABASE_URL and SUPABASE_KEY environment variables are required")
        
        # Log key type for debugging (first few characters only for security)
        key_prefix = supabase_key[:10] + "..." if len(supabase_key) > 10 else "short_key"
        logger.info(f"Initializing Supabase client with key prefix: {key_prefix}")
        
        self.supabase: Client = create_client(supabase_url, supabase_key)
    
    def check_bucket_access(self, bucket_name: str = "pdf_issues") -> dict:
        """
        Check if we can access the specified bucket.
        
        Args:
            bucket_name (str): Name of the bucket to check
            
        Returns:
            dict: Information about bucket access
        """
        try:
            # Try to list files in the bucket
            response = self.supabase.storage.from_(bucket_name).list()
            
            return {
                "success": True,
                "bucket_name": bucket_name,
                "accessible": True,
                "message": f"Successfully accessed bucket '{bucket_name}'"
            }
        except Exception as e:
            return {
                "success": False,
                "bucket_name": bucket_name,
                "accessible": False,
                "error": str(e),
                "message": f"Cannot access bucket '{bucket_name}': {str(e)}"
            }
    
    def upload_pdf(self, pdf_content: bytes, filename: str, bucket_name: str = "pdf_issues") -> str:
        """
        Upload PDF content to Supabase storage and return a signed URL.
        
        Args:
            pdf_content (bytes): PDF file content as bytes
            filename (str): Name for the file in storage
            bucket_name (str): Storage bucket name (default: "pdf_issues")
            
        Returns:
            str: Signed URL to the uploaded PDF (expires in 30 days)
            
        Raises:
            Exception: If upload fails
        """
        try:
            # Ensure filename has .pdf extension
            if not filename.endswith('.pdf'):
                filename += '.pdf'
            
            # Generate a unique filename to avoid conflicts
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_filename = f"{timestamp}_{filename}"
            
            # Upload to Supabase storage
            logger.info(f"Uploading PDF to Supabase storage: {unique_filename}")
            
            response = self.supabase.storage.from_(bucket_name).upload(
                path=unique_filename,
                file=pdf_content,
                file_options={
                    "content-type": "application/pdf",
                    "cache-control": "3600"
                }
            )
            
            # Log the response for debugging
            logger.info(f"Upload response type: {type(response)}")
            if hasattr(response, '__dict__'):
                logger.info(f"Upload response attributes: {response.__dict__}")
            
            # Check for errors - if there's an error attribute and it's not None, that's a failure
            if hasattr(response, 'error') and response.error is not None:
                logger.error(f"Upload error: {response.error}")
                raise Exception(f"Upload failed: {response.error}")
            
            # If we get here, the upload was successful (no error or error is None)
            logger.info("Upload completed successfully")
            
            # Generate a signed URL that expires in 30 days (2592000 seconds)
            # This allows access without requiring authentication
            expires_in_seconds = 30 * 24 * 60 * 60  # 30 days
            
            try:
                signed_url = self.supabase.storage.from_(bucket_name).create_signed_url(
                    path=unique_filename,
                    expires_in=expires_in_seconds
                )
                
                # The response might be a dict with 'signedURL' key or the URL directly
                if isinstance(signed_url, dict) and 'signedURL' in signed_url:
                    final_url = signed_url['signedURL']
                elif isinstance(signed_url, dict) and 'data' in signed_url and signed_url['data']:
                    final_url = signed_url['data']['signedURL'] if 'signedURL' in signed_url['data'] else signed_url['data']
                else:
                    final_url = signed_url
                
                # Validate the URL was generated
                if not final_url:
                    raise Exception("Failed to generate signed URL")
                
                logger.info(f"PDF uploaded successfully. Signed URL (expires in 30 days): {final_url}")
                return final_url
                
            except Exception as url_error:
                logger.error(f"Failed to create signed URL: {url_error}")
                # Fallback to public URL if signed URL fails
                logger.info("Falling back to public URL")
                public_url = self.supabase.storage.from_(bucket_name).get_public_url(unique_filename)
                if not public_url:
                    raise Exception("Failed to generate both signed and public URLs")
                return public_url
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to upload PDF to storage: {error_msg}")
            
            # Provide more specific error messages
            if "403" in error_msg or "Unauthorized" in error_msg:
                raise Exception(f"Storage upload failed: Insufficient permissions. Check bucket '{bucket_name}' settings. Original error: {error_msg}")
            elif "row-level security" in error_msg.lower():
                raise Exception(f"Storage upload failed: Row-level security policy violation. Check bucket RLS policies for '{bucket_name}'. Original error: {error_msg}")
            elif "Upload failed:" in error_msg:
                # Re-raise our own upload errors as-is
                raise
            else:
                raise Exception(f"Storage upload failed: {error_msg}")

    def store_content(self, content, key):
        """Store content in Supabase storage."""
        # This method can be expanded for other storage needs
        pass

    def get_content(self, key):
        """Retrieve content from Supabase storage."""
        # This method can be expanded for retrieval needs
        pass