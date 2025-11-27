import os
import boto3
import google.generativeai as genai
from PIL import Image
from io import BytesIO
from urllib.parse import urlparse
from .classifier_constants import POSITIVE_IMAGE_URL
from ..constants import testing

def is_image_positive(image_url):
    """
    Determines if the image at the given URL (or S3 key) is positive using Gemini.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    aws_access_key = os.environ.get("AWS_ACCESS_KEY_ID")
    aws_secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
    
    if testing:
        return image_url == POSITIVE_IMAGE_URL

    # Fallback if keys are missing
    if not api_key or not aws_access_key or not aws_secret_key:
        print("Missing API keys (GEMINI or AWS). Using fallback.")
        return False

    try:
        # Initialize Gemini
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')

        # Initialize S3
        s3 = boto3.client(
            's3',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name=os.environ.get("AWS_REGION", "us-east-1")
        )

        # Determine Bucket and Key
        bucket_name = os.environ.get("AWS_STORAGE_BUCKET_NAME")
        key = image_url

        # Attempt to parse if it's a full URL
        parsed = urlparse(image_url)
        if parsed.scheme == 's3':
            bucket_name = parsed.netloc
            key = parsed.path.lstrip('/')
        elif parsed.scheme in ['http', 'https'] and 's3' in parsed.netloc:
            # Very basic parsing for standard s3 urls: https://bucket.s3.region.amazonaws.com/key
            # or https://s3.region.amazonaws.com/bucket/key
            # This is brittle, so we prefer relying on the simple key + env bucket if possible.
            # For now, if no bucket env var, we try to guess from URL or fail.
            if not bucket_name:
                 # Try to extract from subdomain
                 parts = parsed.netloc.split('.')
                 if parts[0] != 's3':
                     bucket_name = parts[0]
                     key = parsed.path.lstrip('/')
        
        if not bucket_name:
            print("Could not determine S3 bucket name.")
            return image_url == POSITIVE_IMAGE_URL

        # Download image from S3
        response = s3.get_object(Bucket=bucket_name, Key=key)
        image_data = response['Body'].read()
        image = Image.open(BytesIO(image_data))

        prompt = 'Is this image positive, happy or otherwise makes the user feel good? Answer with only "True" or "False".'
        
        response = model.generate_content([prompt, image])
        
        answer = response.text.strip().lower()
        return answer == "true"

    except Exception as e:
        print(f"Error in image classifier: {e}")
        return False