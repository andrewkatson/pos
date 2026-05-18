import os
import boto3
import logging
from PIL import Image
from io import BytesIO
from urllib.parse import urlparse
from .classifier_constants import POSITIVE_IMAGE_URL, IMAGE_CLASSIFIER_PROMPT
from .classifier_utils import (
    get_available_apis, classify_with_voting, IMAGE_API_DISPATCH,
)
from ..utils import convert_to_bool

logger = logging.getLogger(__name__)


def is_image_positive(image_url):
    testing = os.environ.get("TESTING", False)
    testing = testing if isinstance(testing, bool) else convert_to_bool(testing)

    if testing:
        return image_url == POSITIVE_IMAGE_URL

    available_apis = get_available_apis()

    if not available_apis:
        logger.error("No AI API keys available.")
        return False

    aws_access_key = os.environ.get("AWS_ACCESS_KEY_ID")
    aws_secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")

    if not aws_access_key or not aws_secret_key:
        logger.error("Missing AWS credentials.")
        return False

    try:
        s3 = boto3.client(
            's3',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name=os.environ.get("AWS_REGION", "us-east-1")
        )

        bucket_name = os.environ.get("AWS_STORAGE_BUCKET_NAME")
        key = image_url

        parsed = urlparse(image_url)
        if parsed.scheme == 's3':
            bucket_name = parsed.netloc
            key = parsed.path.lstrip('/')
        elif parsed.scheme in ['http', 'https'] and 's3' in parsed.netloc:
            if not bucket_name:
                parts = parsed.netloc.split('.')
                if parts[0] != 's3':
                    bucket_name = parts[0]
                    key = parsed.path.lstrip('/')

        if not bucket_name:
            logger.error("Could not determine S3 bucket name.")
            return False

        logger.info("Fetching image from S3 with key: %s", key)
        response = s3.get_object(Bucket=bucket_name, Key=key)
        image_data = response['Body'].read()
        image = Image.open(BytesIO(image_data))

        def call_api(api_name):
            try:
                api_func = IMAGE_API_DISPATCH.get(api_name)
                if not api_func:
                    logger.error("Unsupported API name: %s", api_name)
                    return False
                return api_func(image, IMAGE_CLASSIFIER_PROMPT)
            except Exception:
                logger.exception("Error calling %s API for image classification", api_name)
                return False

        return classify_with_voting(available_apis, call_api)

    except Exception:
        logger.exception("Error in image classifier")
        return False
